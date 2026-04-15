import os
import json
from datetime import datetime
from google import genai
from dotenv import load_dotenv

# Configuração de Caminhos
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')

# Carrega chaves do .env (procurando na raiz do projeto)
load_dotenv(os.path.join(BASE_DIR, '.env'))

def get_data_path(filename):
    return os.path.join(DATA_DIR, filename)

def get_report_path(filename):
    return os.path.join(REPORTS_DIR, filename)

def load_config():
    with open(get_data_path('config.json'), 'r', encoding='utf-8') as f:
        return json.load(f)

def load_database():
    path = get_data_path('database.json')
    if not os.path.exists(path):
        return {"articles": []}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_database(db):
    with open(get_data_path('database.json'), 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def load_pool():
    path = get_data_path('pool_de_noticias.json')
    if not os.path.exists(path):
        return {"articles": []}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_pool(pool):
    with open(get_data_path('pool_de_noticias.json'), 'w', encoding='utf-8') as f:
        json.dump(pool, f, indent=2, ensure_ascii=False)

def curate():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Erro: GEMINI_API_KEY não encontrada no ambiente.")
        return

    pool = load_pool()
    if not pool['articles']:
        print("O pool está vazio. Nada para editar.")
        return
    
    client = genai.Client(api_key=api_key)
    MODEL = "gemini-3-flash-preview"

    # Monta o "Bolão" de notícias para a IA
    catalog = ""
    for i, art in enumerate(pool['articles']):
        catalog += f"ID: {i} | Título: {art['title']} | Descrição: {art['description'][:300]}\n---\n"

    prompt = f"""
    Você é o Editor-Chefe de uma agência de notícias espaciais de elite.
    Analise o catálogo abaixo e selecione rigorosamente as 5 notícias mais impactantes do dia.
    
    Critérios:
    1. Inovações técnicas reais.
    2. Grandes movimentações de mercado espacial.
    3. Descobertas científicas validadas.
    
    Para cada selecionada, escreva um 'lead_narrativo' em português do Brasil, num tom jornalístico moderno e instigante, pronto para ser lido em um vídeo.
    
    CATÁLOGO:
    {catalog}
    
    Responda APENAS em JSON seguindo este esquema:
    {{
      "selecionadas": [
        {{
          "id_original": 0,
          "categoria": "Negócios",
          "lead_narrativo": "Texto para o vídeo aqui..."
        }}
      ]
    }}
    """

    print(f"Enviando {len(pool['articles'])} notícias para curadoria do {MODEL}...")
    
    try:
        response = client.models.generate_content(model=MODEL, contents=prompt)
        text = response.text.replace('```json', '').replace('```', '').strip()
        data = json.loads(text)
        
        db = load_database()
        
        selecionadas_finais = []
        indices_para_remover = []
        
        for item in data['selecionadas']:
            idx = item.get('id_original')
            if isinstance(idx, int) and 0 <= idx < len(pool['articles']):
                art = pool['articles'][idx]
                
                art_final = {
                    **art,
                    "status": "publicado",
                    "lead": item.get('lead_narrativo', ''),
                    "category": item.get('categoria', 'Geral'),
                    "data_publicacao": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                
                db['articles'].append(art_final)
                selecionadas_finais.append({"ia": item, "data": art})
                indices_para_remover.append(idx)
                print(f"  [SELECIONADA] {art['title']}")

        # Remove as selecionadas do pool
        new_pool_articles = [art for i, art in enumerate(pool['articles']) if i not in indices_para_remover]
        pool['articles'] = new_pool_articles
        
        save_database(db)
        save_pool(pool)
        
        save_report(selecionadas_finais)
        print("\nCuração concluída. Database atualizado e Relatório gerado!")

    except Exception as e:
        print(f"Erro na curadoria: {e}")
        save_pool(pool)

def save_report(selecionadas_com_dados):
    """Gera um arquivo Markdown bonitão para o usuário ler."""
    hoje = datetime.now().strftime("%d/%m/%Y %H:%M")
    report = f"# 🚀 Relatório da Agência Espacial - {hoje}\n\n"
    report += "Aqui estão as 5 notícias selecionadas para o seu roteiro de hoje:\n\n"
    report += "---\n\n"

    for i, item in enumerate(selecionadas_com_dados):
        art = item['data']
        ia_info = item['ia']
        
        report += f"## {i+1}. {art['title']}\n"
        report += f"**Fonte:** {art['source']} | **Categoria:** {ia_info.get('categoria', 'Geral')}\n\n"
        report += f"> 🎙️ **LEAD PARA O NARRADOR:**\n"
        report += f"> {ia_info.get('lead_narrativo', 'Sem lead disponível.')}\n\n"
        report += f"🔗 [Ler notícia completa]({art['link']})\n\n"
        report += "---\n\n"

    with open(get_report_path('Relatorio_do_Dia.md'), 'w', encoding='utf-8') as f:
        f.write(report)

if __name__ == "__main__":
    curate()
