#!/usr/bin/env python3
"""
Analyse des erreurs dans les logs Scalingo
"""

import re
import sys
from collections import Counter, defaultdict
from datetime import datetime

def parse_error_log(line: str):
    """Parse une ligne de log d'erreur"""
    pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\.\d+ \+\d{4} \w+ \[web-\d+\] ([0-9.]+):\d+ - "([^"]*)" (\d+)'
    
    match = re.match(pattern, line)
    if match:
        timestamp = match.group(1)
        ip = match.group(2)
        request = match.group(3)
        status_code = int(match.group(4))
        return timestamp, ip, request, status_code
    
    return None, None, None, 0

def categorize_error(status_code: int, request: str) -> str:
    """Catégorise le type d'erreur"""
    if status_code == 404:
        if any(x in request for x in ['/favicon.ico', '/apple-touch-icon', '/static/']):
            return "Ressources statiques manquantes"
        elif any(x in request for x in ['wp-', '.php', '.env', 'phpinfo']):
            return "Tentatives d'intrusion"
        elif 'answers/' in request or 'questions/' in request:
            return "Pages de contenu introuvables"
        else:
            return "Pages 404 diverses"
    
    elif status_code == 500:
        if '/forms/' in request and '/dashboard' in request:
            return "Erreurs dashboard formulaires"
        elif '/search/' in request:
            return "Erreurs de recherche"
        else:
            return "Erreurs serveur diverses"
    
    elif status_code == 408:
        if '/search/' in request:
            return "Timeouts de recherche"
        else:
            return "Timeouts divers"
    
    elif status_code == 405:
        return "Méthodes HTTP non autorisées"
    
    else:
        return f"Erreurs {status_code}"

def analyze_errors(filename: str):
    """Analyse les erreurs du fichier de logs"""
    
    error_categories = Counter()
    error_details = defaultdict(list)
    errors_by_hour = defaultdict(int)
    errors_by_ip = Counter()
    
    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            timestamp, ip, request, status_code = parse_error_log(line)
            
            if not ip or status_code < 400:
                continue
            
            # Catégoriser l'erreur
            category = categorize_error(status_code, request)
            error_categories[category] += 1
            
            # Détails par catégorie
            error_details[category].append({
                'timestamp': timestamp,
                'ip': ip,
                'request': request,
                'status': status_code
            })
            
            # Par heure
            hour = timestamp[:13]
            errors_by_hour[hour] += 1
            
            # Par IP
            errors_by_ip[ip] += 1
    
    return error_categories, error_details, errors_by_hour, errors_by_ip

def print_error_report(categories, details, by_hour, by_ip):
    """Affiche le rapport d'erreurs"""
    
    print("=" * 60)
    print("RAPPORT D'ANALYSE DES ERREURS")
    print("=" * 60)
    
    total_errors = sum(categories.values())
    print(f"\n🚨 TOTAL ERREURS: {total_errors}")
    
    print(f"\n📊 ERREURS PAR CATÉGORIE")
    for category, count in categories.most_common():
        percentage = (count / total_errors) * 100
        print(f"   {category}: {count} ({percentage:.1f}%)")
    
    print(f"\n⏰ ERREURS PAR HEURE (top 10)")
    sorted_hours = sorted(by_hour.items(), key=lambda x: x[1], reverse=True)[:10]
    for hour, count in sorted_hours:
        print(f"   {hour}: {count} erreurs")
    
    print(f"\n🌍 TOP IPS AVEC ERREURS")
    for ip, count in by_ip.most_common(10):
        print(f"   {ip}: {count} erreurs")
    
    # Détails par catégorie critique
    print(f"\n🔍 DÉTAILS DES ERREURS CRITIQUES")
    
    # Erreurs 500
    if "Erreurs dashboard formulaires" in details:
        print(f"\n🔴 ERREURS DASHBOARD FORMULAIRES (500)")
        dashboard_errors = details["Erreurs dashboard formulaires"][:5]
        for error in dashboard_errors:
            print(f"   {error['timestamp']} - {error['ip']} - {error['request']}")
    
    if "Erreurs de recherche" in details:
        print(f"\n🔴 ERREURS DE RECHERCHE (500)")
        search_errors = details["Erreurs de recherche"][:5]
        for error in search_errors:
            print(f"   {error['timestamp']} - {error['ip']} - {error['request']}")
    
    # Timeouts 408
    if "Timeouts de recherche" in details:
        print(f"\n⏱️  TIMEOUTS DE RECHERCHE (408)")
        timeout_errors = details["Timeouts de recherche"][:5]
        for error in timeout_errors:
            print(f"   {error['timestamp']} - {error['ip']} - {error['request']}")
    
    # Tentatives d'intrusion
    if "Tentatives d'intrusion" in details:
        print(f"\n🛡️  TENTATIVES D'INTRUSION (404)")
        intrusion_attempts = details["Tentatives d'intrusion"][:10]
        unique_requests = set()
        for error in intrusion_attempts:
            if error['request'] not in unique_requests:
                print(f"   {error['ip']} - {error['request']}")
                unique_requests.add(error['request'])
                if len(unique_requests) >= 5:
                    break
    
    print(f"\n💡 RECOMMANDATIONS")
    
    if "Erreurs dashboard formulaires" in categories:
        print(f"   🔧 Corriger les erreurs 500 sur /forms/*/dashboard")
    
    if "Timeouts de recherche" in categories:
        print(f"   ⚡ Optimiser les performances de recherche (nombreux 408)")
    
    if "Ressources statiques manquantes" in categories:
        print(f"   📁 Ajouter favicon.ico et apple-touch-icon dans /static/")
    
    if "Tentatives d'intrusion" in categories:
        print(f"   🛡️  Considérer un WAF contre les tentatives d'intrusion")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 analyze_errors.py <log_file>")
        sys.exit(1)
    
    log_file = sys.argv[1]
    
    try:
        categories, details, by_hour, by_ip = analyze_errors(log_file)
        print_error_report(categories, details, by_hour, by_ip)
    except FileNotFoundError:
        print(f"Erreur: Fichier {log_file} introuvable")
        sys.exit(1)
    except Exception as e:
        print(f"Erreur lors de l'analyse: {e}")
        sys.exit(1)