#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto-Scraper & Foto-Enricher desde HiFi Corp (www.hificorp.co.za)
Para Catálogo Digital Multiservicios CyM

Busca automáticamente fotos y galerías de alta resolución (HD) en el motor oficial
de HiFi Corp para los productos de catalogo_clientes_sin_comision.json que aún no tengan foto.
"""

import sys
import os
import json
import re
import time
import argparse
import urllib.request
import urllib.parse
from datetime import datetime

# Garantizar salida UTF-8 en terminales de Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# Constantes del motor de búsqueda oficial de HiFi Corp (Klevu v2)
KLEVU_ENDPOINT = "https://eucs7.ksearchnet.com/cs/v2/search"
KLEVU_API_KEY = "klevu-15362133231108501"

HEADERS_KLEVU = {
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.hificorp.co.za/'
}

HEADERS_PAGE = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}

PALABRAS_ACCESORIOS = {
    'case', 'cover', 'protector', 'cable', 'strap', 'stand', 'bracket', 
    'mount', 'pouch', 'sleeve', 'glass', 'adapter', 'skin', 'charger', 'dock',
    'bundle', 'including'
}

COLOR_SYNONYMS = {
    'negro': 'black', 'blanco': 'white', 'azul': 'blue', 'rojo': 'red',
    'gris': 'gray', 'plateado': 'silver', 'dorado': 'gold', 'verde': 'green',
    'morado': 'purple', 'rosa': 'pink', 'amarillo': 'yellow', 'naranja': 'orange',
    'lavender': 'lavender', 'teal': 'teal', 'burgundy': 'burgundy', 'glacier': 'glacier',
    'starlight': 'starlight', 'midnight': 'midnight', 'titanium': 'titanium', 'bronze': 'bronze',
    'graphite': 'graphite', 'space gray': 'space gray', 'space black': 'space black',
    'jet black': 'jet black', 'natural titanium': 'natural titanium', 'desert gold': 'desert gold',
    'cosmic orange': 'cosmic orange', 'deep blue': 'deep blue'
}

def normalizar_texto(t):
    if not t:
        return ""
    t = t.lower()
    t = re.sub(r'[\'\"“”\(\)\[\]·,_\-]', ' ', t)
    return " ".join(t.split())

def buscar_klevu(query, limit=5):
    payload = {
        "context": {"apiKeys": [KLEVU_API_KEY]},
        "recordQueries": [{
            "id": "q",
            "typeOfRequest": "SEARCH",
            "settings": {
                "query": {"term": query},
                "typeOfRecords": ["KLEVU_PRODUCT"],
                "limit": limit
            }
        }]
    }
    try:
        req = urllib.request.Request(
            KLEVU_ENDPOINT,
            data=json.dumps(payload).encode('utf-8'),
            headers=HEADERS_KLEVU
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get('queryResults', [{}])[0].get('records', [])
    except Exception as e:
        return []

def extraer_galeria_producto(product_url):
    """Descarga la página de HiFi Corp y extrae todas las fotos HD de la galería."""
    try:
        req = urllib.request.Request(product_url, headers=HEADERS_PAGE)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            
            # Buscar en el carrusel de Magento/Keen Slider
            matches = re.findall(r'class="gallery--image"[^>]+?(?:data-src|src)="([^"]+)"', html)
            if not matches:
                matches = re.findall(r'(?:data-src|src)="([^"]+)"[^>]+?class="gallery--image"', html)
            
            # Si no encontró por clase, buscar por schema o patrón catalog/product
            if not matches:
                matches = re.findall(r'https?://[^\s\"\'\<\>]+?/api/catalog/product/[^\s\"\'\<\>]+?\.(?:png|jpg|jpeg|webp)', html)
            
            fotos_limpias = []
            for u in matches:
                # Quitar parámetros de reducción/redimensionamiento
                limpia = u.split('?')[0].replace('\\', '').strip()
                if limpia.startswith('http:') and not limpia.startswith('https:'):
                    limpia = 'https:' + limpia[5:]
                if limpia not in fotos_limpias and '/api/catalog/product/' in limpia:
                    fotos_limpias.append(limpia)
                    
            return fotos_limpias
    except Exception as e:
        return []

HEADERS_GOMIBO = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Referer': 'https://www.gomibo.ie/'
}

def buscar_gomibo(query):
    """Busca en el motor oficial de Gomibo (www.gomibo.ie) para telefonía y accesorios."""
    url = f"https://www.gomibo.ie/API/vergelijk/HardwareAndGroupSearch?q={urllib.parse.quote_plus(query)}&ht=ptda"
    try:
        req = urllib.request.Request(url, headers=HEADERS_GOMIBO)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            grupos = data.get('product_groups') or []
            productos = data.get('products') or []
            
            candidatos = []
            for g in grupos:
                candidatos.append({
                    'name': g.get('name') or g.get('title') or '',
                    'url': g.get('url', ''),
                    'imageUrl': g.get('image_src', ''),
                    'brand': '',
                    'source': 'gomibo'
                })
            for p in productos:
                p_url = p.get('url', '')
                if '/accessory-' in p_url or '/cases/' in p_url or '/screenprotectors/' in p_url:
                    continue
                candidatos.append({
                    'name': p.get('name') or p.get('title') or '',
                    'url': p_url,
                    'imageUrl': p.get('image_src', ''),
                    'brand': p.get('brand', ''),
                    'source': 'gomibo'
                })
            return candidatos
    except Exception as e:
        return []

def extraer_galeria_gomibo(product_url):
    """Descarga la página de producto de Gomibo y extrae fotos en resolución completa 0x0."""
    if not product_url:
        return []
    full_url = "https://www.gomibo.ie" + product_url if product_url.startswith('/') else product_url
    try:
        req = urllib.request.Request(full_url, headers=HEADERS_PAGE)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            
            imgs = re.findall(r'https://bsimg\.nl/images/[^\s\"\'\<\>]+', html)
            clean = []
            seen_basenames = set()
            
            for im in imgs:
                if any(x in im for x in ['icon', 'logo', 'badge', 'payment', 'star', 'review', 'close', 'banner', 'avatar', 'shared', 'flags']):
                    continue
                u = re.sub(r'/fit-in/\d+x\d+/[^/]+', '/fit-in/0x0/filters%3Aupscale%28%29', im)
                
                m = re.search(r'/images/([^/]+\.(?:png|jpg|jpeg|webp))/', u)
                if m:
                    base = m.group(1)
                    if base in seen_basenames:
                        continue
                    seen_basenames.add(base)
                
                clean.append(u)
            return clean
    except Exception as e:
        return []

PALABRAS_GENERICAS = {
    'portable', 'bluetooth', 'speaker', 'parlante', 'audifonos', 'headphones',
    'earbuds', 'wireless', 'smart', 'tv', 'celular', 'telefono', 'laptop',
    'notebook', 'desktop', 'screen', 'pantalla', 'official', 'original',
    'esim', '1sim', 'sim', 'wifi', 'cell', 'lte', '5g', '4g', 'gen'
}

def separar_tokens_modelo(texto):
    """Separa números pegados a letras: CLIP5 -> CLIP 5, S24 -> S 24, etc."""
    t = re.sub(r'([a-zA-Z]+)(\d+)', r'\1 \2', texto)
    t = re.sub(r'(\d+)([a-zA-Z]+)', r'\1 \2', t)
    return t

def extraer_palabras_clave_modelo(p_nombre, p_marca):
    """Extrae las palabras distintivas reales del modelo ignorando la marca y palabras genéricas."""
    nombre_limpio = normalizar_texto(separar_tokens_modelo(p_nombre))
    marca_limpia = normalizar_texto(p_marca)
    
    tokens = []
    for w in nombre_limpio.split():
        if w != marca_limpia and w not in PALABRAS_GENERICAS and (len(w) >= 2 or w.isdigit()):
            tokens.append(w)
    return tokens

def evaluar_coincidencia(prod, candidate):
    """Calcula un puntaje estricto de coincidencia entre el producto y el resultado de HiFi Corp."""
    p_marca = normalizar_texto(prod.get('marca', ''))
    p_nombre = normalizar_texto(prod.get('nombre', ''))
    p_variante = normalizar_texto(prod.get('detalles_variante', ''))
    
    c_name = normalizar_texto(candidate.get('name', ''))
    c_brand = normalizar_texto(candidate.get('brand', ''))
    
    # 1. Filtro estricto anti-accesorios
    es_accesorio_candidato = any(w in c_name.split() for w in PALABRAS_ACCESORIOS)
    es_accesorio_catalogo = any(w in p_nombre.split() for w in PALABRAS_ACCESORIOS)
    if es_accesorio_candidato and not es_accesorio_catalogo:
        return -100

    # 2. Filtro de consistencia de categoría
    p_cat = (prod.get('categoria') or '').upper()
    if p_cat == 'AUDIO':
        if any(w in c_name.split() for w in ['phone', 'tablet', 'laptop', 'tv', 'gb', '5g', '4g', 'lte']):
            return -80
    elif p_cat == 'SMARTPHONE':
        if any(w in c_name.split() for w in ['tv', 'laptop', 'tablet', 'watch', 'smartwatch', 'headphone', 'earbuds', 'speaker']):
            return -80
    elif p_cat == 'TELEVISOR':
        if any(w in c_name.split() for w in ['phone', 'tablet', 'laptop', 'watch', 'buds', 'earbuds', 'speaker']):
            return -80
    elif p_cat == 'COMPUTACION':
        if any(w in c_name.split() for w in ['phone', 'tv', 'watch', 'buds', 'earbuds']):
            return -80

    score = 0
    
    # 2. Validación de Marca (con soporte Xiaomi/Redmi/Poco y Anker/Soundcore)
    if p_marca and c_brand:
        if p_marca == c_brand or p_marca in c_name or c_brand in p_marca:
            score += 10
        elif p_marca == 'anker' and ('soundcore' in c_name or 'soundcore' in c_brand):
            score += 10
        elif p_marca == 'xiaomi' and ('poco' in c_name or 'redmi' in c_name or 'poco' in c_brand or 'redmi' in c_brand):
            score += 10
        else:
            return -50 # Marca diferente
    elif p_marca and (p_marca in c_name):
        score += 10
    elif p_marca == 'xiaomi' and ('poco' in c_name or 'redmi' in c_name):
        score += 10
    else:
        return -30

    # 2.5 Validación de Modificadores de Gama/Tier (Pro, Max, Ultra, Mini, Air, Plus, SE, FE)
    TIER_MODIFIERS = {'pro', 'max', 'ultra', 'mini', 'air', 'plus', 'se', 'fe'}
    p_tiers = {w for w in p_nombre.split() if w in TIER_MODIFIERS}
    c_tiers = {w for w in c_name.split() if w in TIER_MODIFIERS}
    if p_tiers != c_tiers:
        return -50 # Conflicto de gama (ej: AirPods Pro vs AirPods normal, o iPhone Pro vs iPhone base)

    # 3. Validación de tokens del modelo
    tokens_modelo = extraer_palabras_clave_modelo(p_nombre, p_marca)
    if not tokens_modelo:
        tokens_modelo = [t for t in p_nombre.split() if t != p_marca and (len(t) >= 2 or t.isdigit())]

    # Palabras alfabéticas clave del modelo (ej: 'clip', 'boombox', 'airpods', 'inspiron', 'katana')
    palabras_modelo = [t for t in tokens_modelo if not t.isdigit()]
    numeros_modelo = [t for t in tokens_modelo if any(c.isdigit() for c in t)]

    # Si hay palabras clave del modelo, AL MENOS UNA DEBE ESTAR en el candidato
    if palabras_modelo:
        coincide_palabra = any(p in c_name.split() or p in c_name for p in palabras_modelo)
        if not coincide_palabra:
            return -40 # Modelo completamente distinto (ej: Partybox en vez de Clip)

    for p in palabras_modelo:
        if p in c_name.split():
            score += 6
        elif p in c_name:
            score += 3

    # 4. Validación de Números de Versión/Serie (ej: 4 vs 3, 580, a15)
    for num in numeros_modelo:
        num_presente = bool(re.search(r'\b' + re.escape(num) + r'\b', c_name))
        if num_presente:
            score += 12
        else:
            # Si es un solo dígito (versión 2, 3, 4, 5) y el candidato tiene un número diferente, penalizar fuerte
            if num.isdigit() and len(num) == 1:
                c_nums = re.findall(r'\b\d\b', c_name)
                if c_nums and num not in c_nums:
                    return -40 # Conflicto de versión (ej: Clip 5 vs Clip 4)

    # 5. Validación y Bonificación por Color
    colores_prod = []
    for esp, eng in COLOR_SYNONYMS.items():
        if esp in p_variante or eng in p_variante:
            colores_prod.append(eng)
    
    colores_candidato = [c for c in COLOR_SYNONYMS.values() if re.search(r'\b' + c + r'\b', c_name)]
    if colores_prod and colores_candidato:
        if any(c in colores_candidato for c in colores_prod):
            score += 15 # Mismo color exacto
        else:
            return -35 # Conflicto evidente de color (ej: catálogo pide GOLD pero candidato es BLACK)
    elif colores_prod:
        # Si el candidato no especifica color, pequeña bonificación si coincide
        for col in colores_prod:
            if col in c_name.split():
                score += 8
                break

    return score

def construir_query_optimizada(prod):
    marca = prod.get('marca', '').strip()
    nombre = prod.get('nombre', '').strip()
    
    # Separar números pegados y normalizar
    nombre_separado = separar_tokens_modelo(nombre)
    tokens_modelo = extraer_palabras_clave_modelo(nombre_separado, marca)
    
    # Combinar marca + las 3-4 palabras clave más importantes del modelo
    query_parts = [marca] + tokens_modelo[:3]
    return " ".join(query_parts)

def procesar_catalogo(archivo_json, marca_filtro=None, categoria_filtro=None, limite=None, dry_run=False, forzar_todas=False):
    if not os.path.exists(archivo_json):
        print(f"❌ Error: No se encontró {archivo_json}")
        return

    with open(archivo_json, 'r', encoding='utf-8') as f:
        catalogo = json.load(f)

    # Filtrar productos candidatos
    candidatos = []
    for p in catalogo:
        tiene_foto = bool(p.get('imagen_principal') or (p.get('galeria_fotos') and len(p.get('galeria_fotos')) > 0))
        if tiene_foto and not forzar_todas:
            continue
        if marca_filtro and marca_filtro.upper() not in p.get('marca', '').upper():
            continue
        if categoria_filtro and categoria_filtro.upper() not in p.get('categoria', '').upper():
            continue
        candidatos.append(p)

    if limite and limite > 0:
        candidatos = candidatos[:limite]

    total = len(candidatos)
    print(f"\n=======================================================")
    print(f"🚀 Iniciando Auto-Scraper HiFi Corp (www.hificorp.co.za)")
    print(f"📦 Total productos a procesar: {total}")
    if marca_filtro:
        print(f"🏷️ Filtro de Marca: {marca_filtro}")
    if categoria_filtro:
        print(f"📁 Filtro de Categoría: {categoria_filtro}")
    print(f"🛡️ Modo: {'[SIMULACIÓN DRY-RUN - No modificará archivos]' if dry_run else '[APLICAR - Guardará cambios en JSON]'}")
    print(f"=======================================================\n")

    encontrados = 0
    total_fotos_agregadas = 0
    mapa_actualizados = {}

    for i, p in enumerate(candidatos, 1):
        sku = p.get('sku')
        marca = p.get('marca')
        nombre = p.get('nombre')
        variante = p.get('detalles_variante', '')
        q = construir_query_optimizada(p)

        print(f"[{i}/{total}] 🔍 Buscando: [{marca}] {nombre} ({variante})")
        print(f"      Término: '{q}'")

        fuente = "HiFi Corp"
        records = buscar_klevu(q, limit=6)
        mejor_candidato = None
        mejor_score = 0

        for r in records:
            s = evaluar_coincidencia(p, r)
            if s > mejor_score:
                mejor_score = s
                mejor_candidato = r

        # Fallback a Gomibo (www.gomibo.ie) si HiFi Corp no tuvo coincidencia segura
        if not mejor_candidato or mejor_score < 10:
            gomibo_records = buscar_gomibo(q)
            for gr in gomibo_records:
                s = evaluar_coincidencia(p, gr)
                if s > mejor_score:
                    mejor_score = s
                    mejor_candidato = gr
                    fuente = "Gomibo"

        if mejor_candidato and mejor_score >= 10:
            c_name = mejor_candidato.get('name')
            c_url = mejor_candidato.get('url')
            galeria = []
            
            if fuente == "Gomibo":
                galeria = extraer_galeria_gomibo(c_url)
                if not galeria and mejor_candidato.get('imageUrl'):
                    raw_img = mejor_candidato.get('imageUrl')
                    galeria = [re.sub(r'/fit-in/\d+x\d+/[^/]+', '/fit-in/0x0/filters%3Aupscale%28%29', raw_img)]
            else:
                galeria = extraer_galeria_producto(c_url)
                klevu_img = mejor_candidato.get('imageUrl', '')
                if not galeria and klevu_img:
                    hd_img = klevu_img.replace('/api/klevu_images/200X200/', '/api/catalog/product/')
                    galeria = [hd_img]

            if galeria:
                encontrados += 1
                total_fotos_agregadas += len(galeria)
                print(f"      ✅ COINCIDENCIA [{fuente}] (Score {mejor_score}): {c_name}")
                print(f"      📸 Fotos obtenidas ({len(galeria)}):")
                for idx, f_url in enumerate(galeria[:3], 1):
                    print(f"         {idx}. {f_url}")
                if len(galeria) > 3:
                    print(f"         ... y {len(galeria) - 3} fotos más.")

                mapa_actualizados[sku] = {
                    'imagen_principal': galeria[0],
                    'galeria_fotos': galeria
                }
            else:
                print(f"      ⚠️ Coincidió con '{c_name}' [{fuente}] pero no se pudieron extraer fotos.")
        else:
            print(f"      ⚪ Sin coincidencia segura en HiFi Corp ni en Gomibo.")

        # Pausa amigable para no sobrecargar el servidor
        time.sleep(0.3)

    print(f"\n=======================================================")
    print(f"🏁 Resumen del Proceso:")
    print(f"   • Productos procesados: {total}")
    print(f"   • Productos con fotos encontradas: {encontrados} ({(encontrados/total*100 if total else 0):.1f}%)")
    print(f"   • Total de fotos HD agregadas: {total_fotos_agregadas}")
    print(f"=======================================================\n")

    if not dry_run and mapa_actualizados:
        # 1. Crear respaldo de seguridad
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = archivo_json.replace('.json', f'.backup_{ts}.json')
        with open(backup_path, 'w', encoding='utf-8') as f_bak:
            json.dump(catalogo, f_bak, ensure_ascii=False, indent=2)
        print(f"🛡️ Respaldo de seguridad creado en: {backup_path}")

        # 2. Aplicar al catálogo
        actualizados_count = 0
        for p in catalogo:
            sku = p.get('sku')
            if sku in mapa_actualizados:
                p['imagen_principal'] = mapa_actualizados[sku]['imagen_principal']
                p['galeria_fotos'] = mapa_actualizados[sku]['galeria_fotos']
                actualizados_count += 1

        with open(archivo_json, 'w', encoding='utf-8') as f_out:
            json.dump(catalogo, f_out, ensure_ascii=False, indent=2)

        print(f"💾 ¡Catálogo {archivo_json} actualizado exitosamente con {actualizados_count} productos!\n")

def main():
    parser = argparse.ArgumentParser(description="Auto-Scraper de fotos HD desde HiFi Corp para Catálogo CyM")
    parser.add_argument("--archivo", default="catalogo_clientes_sin_comision.json", help="Ruta al archivo JSON del catálogo")
    parser.add_argument("--marca", default=None, help="Filtrar por marca (ej: JBL, APPLE, SAMSUNG, SONY, ANKER)")
    parser.add_argument("--categoria", default=None, help="Filtrar por categoría (ej: SMARTPHONE, AUDIO, COMPUTACION)")
    parser.add_argument("--limite", type=int, default=None, help="Número máximo de productos a procesar")
    parser.add_argument("--dry-run", action="store_true", help="Modo simulación (no modifica el JSON)")
    parser.add_argument("--aplicar", action="store_true", help="Aplica directamente las fotos encontradas al archivo JSON")
    parser.add_argument("--forzar-todas", action="store_true", help="Revisar incluso productos que ya tienen fotos")

    args = parser.parse_args()

    # Si no especifica --aplicar ni --dry-run, sugerir o ejecutar en dry-run por seguridad
    is_dry = args.dry_run or (not args.aplicar)
    procesar_catalogo(
        archivo_json=args.archivo,
        marca_filtro=args.marca,
        categoria_filtro=args.categoria,
        limite=args.limite,
        dry_run=is_dry,
        forzar_todas=args.forzar_todas
    )

if __name__ == "__main__":
    main()
