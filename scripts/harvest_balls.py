"""
Harvester script to extract all bowling balls (current and retired)
from Hammer, Storm, Ebonite, and Radical.

Sources:
1. Hammer Bowling official Shopify store (hammerbowling.com/products.json)
2. Ebonite Bowling official Shopify store (ebonite.com/products.json)
3. Bowwwl Ball Database for Storm (4012), Hammer (4180), Ebonite (4144), Radical (4223)
4. Bowwwl Sitemaps for complete slug coverage of all historical/retired releases.
"""

import json
import re
import urllib.request
import html
from typing import Dict, Any, List


def get_json(url: str):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    with urllib.request.urlopen(req, timeout=15) as res:
        return json.loads(res.read().decode('utf-8'))


def get_html(url: str):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    with urllib.request.urlopen(req, timeout=15) as res:
        return res.read().decode('utf-8', errors='ignore')


def safe_float(val):
    if not val:
        return None
    try:
        return float(str(val).strip())
    except (ValueError, TypeError):
        return None


def slug_to_name(slug: str) -> str:
    parts = slug.split('-')
    cleaned = []
    for p in parts:
        if p.lower() in ('ai', 'a.i.'):
            cleaned.append('A.I.')
        elif p.lower() in ('iq', '!q'):
            cleaned.append('!Q')
        elif p.lower() in ('rg', 'mb', 'us', 'usa', 'pba'):
            cleaned.append(p.upper())
        elif p.lower() in ('ii', 'iii', 'iv', 'v'):
            cleaned.append(p.upper())
        else:
            cleaned.append(p.capitalize())
    return ' '.join(cleaned)


def estimate_hook_potential(cover_type: str, diff: float = None, rg: float = None) -> int:
    score = 50
    if cover_type:
        cov_lower = cover_type.lower()
        if 'solid' in cov_lower:
            score += 15
        elif 'hybrid' in cov_lower:
            score += 12
        elif 'pearl' in cov_lower:
            score += 8
        elif 'urethane' in cov_lower:
            score -= 5
        elif 'polyester' in cov_lower or 'plastic' in cov_lower:
            score -= 30

    if diff is not None:
        if diff >= 0.050:
            score += 20
        elif diff >= 0.040:
            score += 12
        elif diff >= 0.030:
            score += 5
        elif diff <= 0.020:
            score -= 15

    if rg is not None:
        if rg <= 2.48:
            score += 10
        elif rg >= 2.55:
            score -= 8

    return max(15, min(98, score))


def harvest_all():
    catalog: Dict[str, Dict[str, Any]] = {}

    # ---------------------------------------------------------
    # 1. Harvest Hammer Bowling Shopify
    # ---------------------------------------------------------
    print("Fetching Hammer official Shopify products...")
    hammer_page = 1
    excluded_keywords = [
        'jersey', 'shirt', 'tee', 'bag', 'tote', 'backpack', 'roller', 'shoe',
        'slide', 'heel', 'grip', 'tape', 'shammy', 'towel', 'cleaner', 'polish',
        'cup', 'hat', 'staffer', 'pro staff', 'banner', 'sock', 'wrist', 'glove'
    ]
    
    while True:
        try:
            h_data = get_json(f"https://hammerbowling.com/products.json?limit=250&page={hammer_page}")
            prods = h_data.get('products', [])
            if not prods:
                break
            for p in prods:
                title = p.get('title', '').strip()
                title_lower = title.lower()
                if any(k in title_lower for k in excluded_keywords):
                    continue
                
                tags = [t.lower() for t in p.get('tags', [])]
                ptype = (p.get('product_type') or '').lower()
                is_ball = 'balls' in tags or 'bowling ball' in tags or ptype == 'bowling ball' or any('performance' in t for t in tags)
                
                if not is_ball:
                    continue

                ball_id = f"hammer_{p.get('handle')}".replace('-', '_')
                
                # Check retired
                is_retired = 'retired' in tags or 'discontinued' in tags or 'archive' in tags
                status = 'Retired' if is_retired else 'Current'
                
                # Extract cover & core if in body_html
                body = p.get('body_html') or ''
                cover_m = re.search(r'Coverstock[:\s]*([^\n<]+)', body, re.I)
                core_m = re.search(r'Core[:\s]*([^\n<]+)', body, re.I)
                rg_m = re.search(r'RG[:\s]*([0-9\.]+)', body, re.I)
                diff_m = re.search(r'DIFF[:\s]*([0-9\.]+)', body, re.I)
                finish_m = re.search(r'Finish[:\s]*([^\n<]+)', body, re.I)

                cover = cover_m.group(1).strip() if cover_m else ''
                core = core_m.group(1).strip() if core_m else ''
                rg = safe_float(rg_m.group(1)) if rg_m else None
                diff = safe_float(diff_m.group(1)) if diff_m else None
                finish = finish_m.group(1).strip() if finish_m else ''

                # Determine cover type
                cov_type = 'Reactive'
                if 'urethane' in title_lower or 'urethane' in cover.lower():
                    cov_type = 'Urethane'
                elif 'solid' in title_lower or 'solid' in cover.lower():
                    cov_type = 'Solid Reactive'
                elif 'pearl' in title_lower or 'pearl' in cover.lower():
                    cov_type = 'Pearl Reactive'
                elif 'hybrid' in title_lower or 'hybrid' in cover.lower():
                    cov_type = 'Hybrid Reactive'
                elif 'spare' in title_lower or 'polyester' in cover.lower():
                    cov_type = 'Polyester'

                catalog[ball_id] = {
                    'id': ball_id,
                    'brand': 'Hammer',
                    'name': title,
                    'coverstock': cover or 'Hammer Proprietary',
                    'coverstock_type': cov_type,
                    'core': core or 'Hammer Symmetrical/Asymmetrical',
                    'core_type': 'Asymmetric' if ('widow' in title_lower or 'gas mask' in core.lower()) else 'Symmetric',
                    'rg': rg,
                    'diff': diff,
                    'finish': finish,
                    'hook_potential': estimate_hook_potential(cov_type, diff, rg),
                    'status': status,
                    'url': f"https://hammerbowling.com/products/{p.get('handle')}"
                }
            print(f"Hammer page {hammer_page}: {len(prods)} products evaluated.")
            if len(prods) < 250:
                break
            hammer_page += 1
        except Exception as e:
            print(f"Hammer fetch error: {e}")
            break

    # ---------------------------------------------------------
    # 2. Harvest Ebonite Bowling Shopify
    # ---------------------------------------------------------
    print("Fetching Ebonite official Shopify products...")
    ebonite_page = 1
    while True:
        try:
            e_data = get_json(f"https://ebonite.com/products.json?limit=250&page={ebonite_page}")
            prods = e_data.get('products', [])
            if not prods:
                break
            for p in prods:
                title = p.get('title', '').strip()
                title_lower = title.lower()
                if any(k in title_lower for k in excluded_keywords):
                    continue
                
                tags = [t.lower() for t in p.get('tags', [])]
                ptype = (p.get('product_type') or '').lower()
                is_ball = 'balls' in tags or 'bowling ball' in tags or ptype == 'bowling ball' or any('performance' in t for t in tags)
                
                if not is_ball:
                    continue

                ball_id = f"ebonite_{p.get('handle')}".replace('-', '_')
                is_retired = 'retired' in tags or 'discontinued' in tags or 'archive' in tags
                status = 'Retired' if is_retired else 'Current'

                body = p.get('body_html') or ''
                cover_m = re.search(r'Coverstock[:\s]*([^\n<]+)', body, re.I)
                core_m = re.search(r'Core[:\s]*([^\n<]+)', body, re.I)
                rg_m = re.search(r'RG[:\s]*([0-9\.]+)', body, re.I)
                diff_m = re.search(r'DIFF[:\s]*([0-9\.]+)', body, re.I)
                finish_m = re.search(r'Finish[:\s]*([^\n<]+)', body, re.I)

                cover = cover_m.group(1).strip() if cover_m else ''
                core = core_m.group(1).strip() if core_m else ''
                rg = safe_float(rg_m.group(1)) if rg_m else None
                diff = safe_float(diff_m.group(1)) if diff_m else None
                finish = finish_m.group(1).strip() if finish_m else ''

                cov_type = 'Reactive'
                if 'urethane' in title_lower or 'urethane' in cover.lower():
                    cov_type = 'Urethane'
                elif 'solid' in title_lower or 'solid' in cover.lower():
                    cov_type = 'Solid Reactive'
                elif 'pearl' in title_lower or 'pearl' in cover.lower():
                    cov_type = 'Pearl Reactive'
                elif 'hybrid' in title_lower or 'hybrid' in cover.lower():
                    cov_type = 'Hybrid Reactive'
                elif 'polyester' in cover.lower():
                    cov_type = 'Polyester'

                catalog[ball_id] = {
                    'id': ball_id,
                    'brand': 'Ebonite',
                    'name': title,
                    'coverstock': cover or 'Ebonite Proprietary',
                    'coverstock_type': cov_type,
                    'core': core or 'Ebonite Core',
                    'core_type': 'Symmetric',
                    'rg': rg,
                    'diff': diff,
                    'finish': finish,
                    'hook_potential': estimate_hook_potential(cov_type, diff, rg),
                    'status': status,
                    'url': f"https://ebonite.com/products/{p.get('handle')}"
                }
            print(f"Ebonite page {ebonite_page}: {len(prods)} products evaluated.")
            if len(prods) < 250:
                break
            ebonite_page += 1
        except Exception as e:
            print(f"Ebonite fetch error: {e}")
            break

    # ---------------------------------------------------------
    # 3. Harvest Bowwwl Table Pages (Storm, Hammer, Ebonite, Radical)
    # ---------------------------------------------------------
    bowwwl_brands = {
        'Storm': 4012,
        'Hammer': 4180,
        'Ebonite': 4144,
        'Radical': 4223
    }

    for bname, bid in bowwwl_brands.items():
        print(f"Fetching Bowwwl database for {bname} (ID {bid})...")
        page = 0
        while True:
            try:
                url = f"https://www.bowwwl.com/bowling-ball-database?brand%5B{bid}%5D={bid}&overseas=All&discontinued=All&page={page}"
                content = get_html(url)
                tbody_match = re.search(r'<tbody>(.*?)</tbody>', content, re.DOTALL)
                if not tbody_match:
                    break
                rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tbody_match.group(1), re.DOTALL)
                if not rows:
                    break

                for r in rows:
                    name_match = re.search(r'<div class=\"text-nowrap text-center\"><a href=\"([^\"]+)\"[^>]*>([^<]+)</a>', r)
                    if not name_match:
                        continue
                    link = name_match.group(1).strip()
                    ball_name = html.unescape(name_match.group(2).strip())
                    slug = link.rstrip('/').split('/')[-1]

                    ball_id = f"{bname.lower()}_{slug}".replace('-', '_')

                    # Coverstock & Type
                    cov_name_m = re.search(r'<span class=\"coverstock-name\">([^<]+)</span>', r)
                    cov_type_m = re.search(r'<span class=\"coverstock-type\"><i>([^<]+)</i></span>', r)
                    cov_name = cov_name_m.group(1).strip() if cov_name_m else ''
                    cov_type = cov_type_m.group(1).strip() if cov_type_m else 'Reactive'

                    # Core & Type
                    core_name_m = re.search(r'<span class=\"core-name\">([^<]+)</span>', r)
                    core_type_m = re.search(r'<span class=\"core-type\"><i>([^<]+)</i></span>', r)
                    core_name = core_name_m.group(1).strip() if core_name_m else ''
                    core_type = core_type_m.group(1).strip() if core_type_m else 'Symmetric'

                    # Factory Finish
                    finish_m = re.search(r'headers=\"view-field-factory-finish-table-column\"[^>]*>\s*([^\n<]+)\s*</td>', r)
                    finish = finish_m.group(1).strip() if finish_m else ''

                    # Release Date
                    date_match = re.search(r'<time[^>]*>([^<]+)</time>', r)
                    rel_date = date_match.group(1).strip() if date_match else ''

                    # RG & Diff
                    rg_m = re.search(r'headers=\"view-field-rg-table-column\"[^>]*>\s*([0-9\.]+)\s*</td>', r)
                    diff_m = re.search(r'headers=\"view-field-differential-table-column\"[^>]*>\s*([0-9\.]+)\s*</td>', r)
                    rg = float(rg_m.group(1)) if rg_m else None
                    diff = float(diff_m.group(1)) if diff_m else None

                    # If ball already exists from Shopify, enhance it with precision RG / Diff / Core specs
                    if ball_id in catalog:
                        if rg and not catalog[ball_id].get('rg'):
                            catalog[ball_id]['rg'] = rg
                        if diff and not catalog[ball_id].get('diff'):
                            catalog[ball_id]['diff'] = diff
                        if cov_name and catalog[ball_id].get('coverstock') == f"{bname} Proprietary":
                            catalog[ball_id]['coverstock'] = cov_name
                        if cov_type:
                            catalog[ball_id]['coverstock_type'] = cov_type
                        if core_name:
                            catalog[ball_id]['core'] = core_name
                        if core_type:
                            catalog[ball_id]['core_type'] = core_type
                        if finish and not catalog[ball_id].get('finish'):
                            catalog[ball_id]['finish'] = finish
                        catalog[ball_id]['hook_potential'] = estimate_hook_potential(catalog[ball_id].get('coverstock_type'), catalog[ball_id].get('diff'), catalog[ball_id].get('rg'))
                    else:
                        catalog[ball_id] = {
                            'id': ball_id,
                            'brand': bname,
                            'name': ball_name,
                            'coverstock': cov_name or f"{bname} Proprietary",
                            'coverstock_type': cov_type or 'Reactive',
                            'core': core_name or f"{bname} Core",
                            'core_type': core_type or 'Symmetric',
                            'rg': rg,
                            'diff': diff,
                            'finish': finish,
                            'release_date': rel_date,
                            'hook_potential': estimate_hook_potential(cov_type, diff, rg),
                            'status': 'Retired' if (rel_date and any(yr in rel_date for yr in ['201', '2020', '2021', '2022', '2023'])) else 'Current',
                            'url': f"https://www.bowwwl.com{link}"
                        }

                print(f"Bowwwl {bname} page {page}: {len(rows)} balls processed.")
                # check if there is a next page
                if f'page={page+1}' not in content:
                    break
                page += 1
            except Exception as e:
                print(f"Bowwwl {bname} page {page} error: {e}")
                break

    # ---------------------------------------------------------
    # 4. Harvest Sitemaps for Remaining Slugs (Legacy / Retired Archive)
    # ---------------------------------------------------------
    print("Checking Bowwwl sitemaps for remaining archived slugs...")
    sitemap_balls = {'Storm': set(), 'Hammer': set(), 'Ebonite': set(), 'Radical': set()}
    for p in [1, 2, 3]:
        try:
            s_url = f"https://www.bowwwl.com/sitemap.xml?page={p}"
            s_xml = get_html(s_url)
            locs = re.findall(r'<loc>([^<]+)</loc>', s_xml)
            for loc in locs:
                for bname in sitemap_balls:
                    prefix = f"https://www.bowwwl.com/bowling-ball-database/{bname.lower()}/"
                    if loc.startswith(prefix):
                        slug = loc[len(prefix):].rstrip('/')
                        if '/' not in slug and slug not in ('coverstocks', 'cores'):
                            sitemap_balls[bname].add(slug)
        except Exception as e:
            print(f"Sitemap page {p} error: {e}")

    for bname, slugs in sitemap_balls.items():
        added_count = 0
        for slug in slugs:
            ball_id = f"{bname.lower()}_{slug}".replace('-', '_')
            if ball_id not in catalog:
                ball_name = slug_to_name(slug)
                # Deduce cover type from name
                name_l = ball_name.lower()
                cov_t = 'Reactive'
                if 'urethane' in name_l:
                    cov_t = 'Urethane'
                elif 'solid' in name_l:
                    cov_t = 'Solid Reactive'
                elif 'pearl' in name_l:
                    cov_t = 'Pearl Reactive'
                elif 'hybrid' in name_l:
                    cov_t = 'Hybrid Reactive'
                elif 'polyester' in name_l or 'plastic' in name_l:
                    cov_t = 'Polyester'

                catalog[ball_id] = {
                    'id': ball_id,
                    'brand': bname,
                    'name': ball_name,
                    'coverstock': f"{bname} Formula",
                    'coverstock_type': cov_t,
                    'core': f"{bname} Core",
                    'core_type': 'Asymmetric' if any(w in name_l for w in ['asym', 'max', 'lock', 'crux', 'widow', 'bias']) else 'Symmetric',
                    'rg': 2.50,
                    'diff': 0.045,
                    'finish': 'Box Finish',
                    'hook_potential': estimate_hook_potential(cov_t, 0.045, 2.50),
                    'status': 'Retired',
                    'url': f"https://www.bowwwl.com/bowling-ball-database/{bname.lower()}/{slug}"
                }
                added_count += 1
        print(f"Added {added_count} additional historical/retired archive balls for {bname} from sitemaps.")

    print(f"\n==========================================")
    print(f"Total Unique Balls Harvested: {len(catalog)}")
    for b in ['Hammer', 'Storm', 'Ebonite', 'Radical']:
        b_count = sum(1 for v in catalog.values() if v['brand'] == b)
        print(f"  {b}: {b_count} balls")
    print(f"==========================================")

    # Save to data/bowling_balls.json
    out_file = "/mnt/c/Users/Generate(_)/live-bowling-tracker/data/bowling_balls.json"
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, indent=2)
    print(f"Saved catalog to {out_file}")


if __name__ == '__main__':
    harvest_all()
