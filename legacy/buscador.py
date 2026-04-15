import os
import json
import time
import xml.etree.ElementTree as ET
import requests
from dotenv import load_dotenv
from google import genai

# Carrega as variáveis de ambiente do arquivo .env
# O cliente lê GEMINI_API_KEY automaticamente do ambiente
load_dotenv()

# Configuração do novo SDK do Gemini
API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY and API_KEY != "SUA_CHAVE_AQUI":
    client = genai.Client()
    MODEL = "gemini-3-flash-preview"
    ai_enabled = True
else:
    client = None
    ai_enabled = False
    print("AVISO: GEMINI_API_KEY não configurada. O filtro de IA será ignorado.")


def load_config():
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)


def load_database():
    with open('database.json', 'r', encoding='utf-8') as f:
        return json.load(f)


def save_database(db):
    with open('database.json', 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


def fetch_rss(feed_config):
    """Lê o RSS de um arquivo local ou de uma URL."""
    try:
        local_path = feed_config.get('local_path')
        if local_path and os.path.exists(local_path):
            print(f"Lendo feed local: {local_path}")
            tree = ET.parse(local_path)
            return tree.getroot()

        print(f"Buscando feed remoto: {feed_config['url']}")
        response = requests.get(feed_config['url'], timeout=10)
        response.raise_for_status()
        return ET.fromstring(response.content)
    except Exception as e:
        print(f"Erro ao buscar feed {feed_config['name']}: {e}")
        return None


def build_filter_prompt(title, description):
    """Monta o prompt de filtragem para uma notícia."""
    return f"""Você é um editor de um canal de notícias sobre exploração espacial e a indústria aeroespacial.
Analise se a notícia abaixo é relevante para esse canal. Considere relevante:
- Missões, foguetes, satélites, astronautas e descobertas científicas.
- Geopolítica e políticas que afetem o setor espacial.
- Negócios, contratos e investimentos do setor aeroespacial.
- Qualquer evento externo (economia, política, etc.) com impacto direto no setor.

Título: {title}
Resumo: {description[:500]}

Responda SOMENTE com um JSON válido, sem markdown, sem explicações:
{{"relevante": true, "motivo": "...", "categoria": "Missão|Negócios|Ciência|Política|Tecnologia|Geral"}}"""


def filter_with_batch_api(candidates):
    """
    Usa a Batch API do Gemini para filtrar todas as notícias de uma vez.
    Muito mais eficiente que chamadas individuais — evita o limite de RPM
    e custa 50% menos que o modo padrão.
    """
    if not candidates:
        return {}

    print(f"\n→ Enviando {len(candidates)} notícias para a Batch API do Gemini...")
    print("  (O processamento é assíncrono — aguardaremos a conclusão do job)")

    # Monta a lista de requests para o batch
    inline_requests = []
    keys = []
    for i, candidate in enumerate(candidates):
        key = f"news-{i}"
        keys.append(key)
        inline_requests.append({
            'contents': [{
                'parts': [{'text': build_filter_prompt(candidate['title'], candidate['description'])}],
                'role': 'user'
            }]
        })

    try:
        # Cria o job em lote (Batch API)
        batch_job = client.batches.create(
            model=MODEL,
            src=inline_requests,
            config={'display_name': f"buscador-noticias-{int(time.time())}"}
        )
        job_name = batch_job.name
        print(f"  Job criado: {job_name}")

        # Aguarda o job terminar (polling)
        TERMINAL_STATES = ('JOB_STATE_SUCCEEDED', 'JOB_STATE_FAILED',
                           'JOB_STATE_CANCELLED', 'JOB_STATE_EXPIRED')
        wait_seconds = 10
        while True:
            job = client.batches.get(name=job_name)
            state = job.state.name
            if state in TERMINAL_STATES:
                break
            print(f"  Estado atual: {state}. Aguardando {wait_seconds}s...")
            time.sleep(wait_seconds)
            wait_seconds = min(wait_seconds * 2, 60)  # Backoff: 10s, 20s, 40s, 60s

        if state != 'JOB_STATE_SUCCEEDED':
            print(f"  ERRO: Job terminou com estado '{state}'. Todas as notícias serão incluídas.")
            return {key: {'relevante': True, 'motivo': 'Erro no job', 'categoria': 'Geral'} for key in keys}

        print(f"  Job concluído com sucesso!")

        # Processa as respostas
        results = {}
        for i, inline_response in enumerate(job.dest.inlined_responses):
            key = keys[i]
            try:
                if inline_response.response:
                    text = inline_response.response.text.strip()
                    # Remove possíveis marcações de markdown
                    text = text.replace('```json', '').replace('```', '').strip()
                    result = json.loads(text)
                    results[key] = result
                else:
                    results[key] = {'relevante': True, 'motivo': 'Sem resposta', 'categoria': 'Geral'}
            except (json.JSONDecodeError, Exception) as e:
                print(f"  Aviso: Erro ao processar resposta da notícia {key}: {e}")
                results[key] = {'relevante': True, 'motivo': 'Erro no parse', 'categoria': 'Geral'}

        return results

    except Exception as e:
        print(f"  ERRO na Batch API: {e}")
        print("  Incluindo todas as notícias por segurança.")
        return {key: {'relevante': True, 'motivo': 'Erro na API', 'categoria': 'Geral'} for key in keys}


def process_feeds():
    config = load_config()
    db = load_database()
    existing_links = {a['link'] for a in db['articles']}

    # Passo 1: Coleta de candidatos (sem chamar a IA ainda)
    candidates = []
    for feed in config['feeds']:
        root = fetch_rss(feed)
        if root is None:
            continue

        items = root.findall('.//item')
        max_items = config['settings']['max_news_per_source']

        for item in items[:max_items]:
            title = item.find('title').text if item.find('title') is not None else ""
            link = item.find('link').text if item.find('link') is not None else ""
            description = item.find('description').text if item.find('description') is not None else ""
            pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ""

            # Ignora notícias já vistas
            if link in existing_links:
                continue

            candidates.append({
                'title': title,
                'link': link,
                'description': description,
                'pub_date': pub_date,
                'source': feed['name']
            })
            existing_links.add(link)

    if not candidates:
        print("Nenhuma notícia nova encontrada. Database já está atualizada.")
        return

    print(f"\n{len(candidates)} notícias novas coletadas.")

    # Passo 2: Filtragem em lote (ou inclusão direta se IA desativada)
    if ai_enabled:
        results = filter_with_batch_api(candidates)
    else:
        # Sem IA, inclui tudo
        results = {f"news-{i}": {'relevante': True, 'motivo': 'Sem filtro', 'categoria': 'Geral'}
                   for i in range(len(candidates))}

    # Passo 3: Salva as notícias relevantes no banco
    new_count = 0
    for i, candidate in enumerate(candidates):
        key = f"news-{i}"
        result = results.get(key, {'relevante': True, 'motivo': 'Sem resultado', 'categoria': 'Geral'})

        if result.get('relevante', True):
            db['articles'].append({
                "title": candidate['title'],
                "link": candidate['link'],
                "description": candidate['description'],
                "pub_date": candidate['pub_date'],
                "source": candidate['source'],
                "category": result.get('categoria', 'Geral'),
                "ai_reason": result.get('motivo', ''),
                "status": "selected"
            })
            new_count += 1
        else:
            print(f"  [IGNORADA] {candidate['title'][:60]}...")

    if new_count > 0:
        save_database(db)
        print(f"\nConcluído! {new_count} de {len(candidates)} notícias salvas no database.")
    else:
        print("\nNenhuma notícia passou pelo filtro.")


if __name__ == "__main__":
    process_feeds()
