#!/usr/bin/env python3
"""
Script d'analyse des visiteurs à partir des logs Scalingo
"""

import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, Set, List, Tuple

def parse_log_line(line: str) -> Tuple[str, str, str, int]:
    """Parse une ligne de log et retourne (timestamp, IP, method+path, status_code)"""
    # Pattern pour parser les logs Scalingo
    pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\.\d+ \+\d{4} \w+ \[web-\d+\] ([0-9.]+):\d+ - "(\w+ [^"]*) HTTP/1\.[01]" (\d+)'
    
    match = re.match(pattern, line)
    if match:
        timestamp = match.group(1)
        ip = match.group(2)
        request = match.group(3)
        status_code = int(match.group(4))
        return timestamp, ip, request, status_code
    
    return None, None, None, 0

def is_bot_or_crawler(user_agent: str, ip: str) -> bool:
    """Détermine si la requête vient d'un bot (basique)"""
    # Certaines IPs connues de bots/crawlers
    bot_ips = {'161.97.66.6'}  # Cette IP fait beaucoup de requêtes séquentielles
    
    return ip in bot_ips

def analyze_logs(filename: str) -> Dict:
    """Analyse le fichier de logs et retourne les statistiques"""
    
    # Compteurs
    unique_ips = set()
    requests_by_hour = defaultdict(int)
    requests_by_ip = Counter()
    pages_accessed = Counter()
    status_codes = Counter()
    bot_requests = 0
    human_requests = 0
    unique_human_ips = set()
    
    # Période d'analyse
    start_time = None
    end_time = None
    
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
                
            timestamp, ip, request, status_code = parse_log_line(line)
            
            if not ip:
                continue
            
            # Mettre à jour les timestamps
            if start_time is None:
                start_time = timestamp
            end_time = timestamp
            
            # Ajouter l'IP
            unique_ips.add(ip)
            requests_by_ip[ip] += 1
            status_codes[status_code] += 1
            
            # Extraire l'heure
            hour = timestamp[:13]  # YYYY-MM-DD HH
            requests_by_hour[hour] += 1
            
            # Extraire la page
            if request and status_code == 200:
                method, path = request.split(' ', 1) if ' ' in request else ('GET', request)
                if method == 'GET' and not path.startswith('/static/'):
                    pages_accessed[path] += 1
            
            # Détecter les bots
            if is_bot_or_crawler('', ip):
                bot_requests += 1
            else:
                human_requests += 1
                unique_human_ips.add(ip)
    
    return {
        'period': f"{start_time} → {end_time}",
        'total_requests': len(open(filename).readlines()),
        'unique_ips': len(unique_ips),
        'unique_human_visitors': len(unique_human_ips),
        'bot_requests': bot_requests,
        'human_requests': human_requests,
        'requests_by_hour': dict(sorted(requests_by_hour.items())),
        'top_ips': requests_by_ip.most_common(10),
        'top_pages': pages_accessed.most_common(10),
        'status_codes': dict(status_codes),
        'all_ips': list(unique_ips)
    }

def print_report(stats: Dict):
    """Affiche le rapport d'analyse"""
    
    print("=" * 60)
    print("RAPPORT D'ANALYSE DES VISITEURS")
    print("=" * 60)
    
    print(f"\n📊 PÉRIODE D'ANALYSE")
    print(f"   {stats['period']}")
    
    print(f"\n👥 VISITEURS UNIQUES")
    print(f"   Total IPs uniques: {stats['unique_ips']}")
    print(f"   Visiteurs humains estimés: {stats['unique_human_visitors']}")
    print(f"   Ratio humain/bot: {stats['human_requests']}/{stats['bot_requests']}")
    
    print(f"\n📈 REQUÊTES PAR HEURE")
    for hour, count in stats['requests_by_hour'].items():
        print(f"   {hour}: {count} requêtes")
    
    print(f"\n🔝 TOP IPS")
    for ip, count in stats['top_ips']:
        is_bot = "🤖" if ip in {'161.97.66.6'} else "👤"
        print(f"   {is_bot} {ip}: {count} requêtes")
    
    print(f"\n📄 PAGES LES PLUS CONSULTÉES")
    for page, count in stats['top_pages']:
        print(f"   {page}: {count} vues")
    
    print(f"\n📋 CODES DE STATUT")
    for code, count in sorted(stats['status_codes'].items()):
        print(f"   HTTP {code}: {count}")
    
    print(f"\n🌍 TOUTES LES IPS DETECTÉES")
    for ip in sorted(stats['all_ips']):
        is_bot = "🤖" if ip in {'161.97.66.6'} else "👤"
        print(f"   {is_bot} {ip}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 analyze_visitors.py <log_file>")
        sys.exit(1)
    
    log_file = sys.argv[1]
    
    try:
        stats = analyze_logs(log_file)
        print_report(stats)
    except FileNotFoundError:
        print(f"Erreur: Fichier {log_file} introuvable")
        sys.exit(1)
    except Exception as e:
        print(f"Erreur lors de l'analyse: {e}")
        sys.exit(1)