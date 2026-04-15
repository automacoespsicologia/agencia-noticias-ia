import os
import json
import xml.etree.ElementTree as ET
import requests
from datetime import datetime

# Configuração de Caminhos
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')

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

def load_pool():
    path = get_data_path('pool_de_noticias.json')
    if not os.path.exists(path):
        return {"articles": []}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_pool(pool):
    with open(get_data_path('pool_de_noticias.json'), 'w', encoding='utf-8') as f:
        json.dump(pool, f, indent=2, ensure_ascii=False)

def fetch_rss(feed_config):
    """Lê o RSS de um arquivo local ou de uma URL."""
    try:
        local_name = feed_config.get('local_path') # Ex: SpaceNews.xml
        if local_name:
            local_path = get_data_path(local_name)
            if os.path.exists(local_path):
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

def collect():
    # Garante que as pastas existam
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    config = load_config()
    db = load_database()
    pool = load_pool()
    
    known_links = {a['link'] for a in db['articles']}
    known_links.update({a['link'] for a in pool['articles']})
    
    new_count = 0
    today_str = datetime.now().strftime("%Y-%m-%d")
    
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

            if link in known_links:
                continue

            pool['articles'].append({
                'title': title,
                'link': link,
                'description': description,
                'pub_date': pub_date,
                'source': feed['name'],
                'data_coleta': today_str,
                'tentativas': 0
            })
            known_links.add(link)
            new_count += 1

    if new_count > 0:
        save_pool(pool)
    
    # Sempre atualiza o relatório Markdown
    save_pool_report(load_pool())
    
    if new_count > 0:
        print(f"Sucesso! {new_count} novas notícias adicionadas ao pool.")
    else:
        print("Nenhuma notícia inédita encontrada. O relatório foi atualizado com o balde atual.")

def save_pool_report(pool):
    """Gera uma lista amigável com resumos para o usuário ler o que está no balde."""
    hoje = datetime.now().strftime("%d/%m/%Y %H:%M")
    report = f"# 📥 Balde de Notícias Brutas - {hoje}\n\n"
    report += f"Atualmente existem **{len(pool['articles'])}** notícias aguardando a curadoria do Editor.\n\n"
    report += "---\n\n"
    
    for art in pool['articles']:
        report += f"### {art['title']}\n"
        report += f"**Fonte:** {art['source']}\n\n"
        resumo = art['description'].replace('<p>', '').replace('</p>', '').split('<')[0]
        report += f"{resumo[:400]}...\n\n"
        report += f"🔗 [Link da Notícia]({art['link']})\n\n"
        report += "---\n\n"

    report += "\n*Rode o `run_agency.py` para que a IA selecione as melhores desta lista.*"

    with open(get_report_path('Pool_do_Dia.md'), 'w', encoding='utf-8') as f:
        f.write(report)

if __name__ == "__main__":
    collect()
