#!/usr/bin/env python3
"""
Скрипт для отправки outreach emails через Gmail API
Для топ-5 компаний: Proton, EFF, Mullvad VPN, Access Now, Signal Foundation
"""

import os
import base64
import csv
from datetime import datetime, timedelta
from pathlib import Path

# Gmail API imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from email.mime.text import MIMEText

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

# Конфигурация emails
EMAILS_CONFIG = [
    {
        "company": "Proton",
        "contact": "Andy Yen",
        "email": "andy.yen@proton.ch",
        "subject": "Post-Quantum Mesh for Proton's 100M+ Users",
        "body": """Hi Andy,

Proton protects 100M+ users (CERN roots align with x0tta6bl4's self-healing architecture). 
As quantum computers threaten current encryption (PGP/WireGuard), I built x0tta6bl4 — 
the first production-ready mesh network with NIST-standard post-quantum cryptography (ML-KEM-768).

Key benefits for Proton:
- Quantum-safe encryption (protected for 50+ years)
- Self-healing architecture (MTTR <3 minutes)
- NIST FIPS 203/204 compliant

Would you be open to a 15-minute demo call this week?

Best,
x0tta6bl4 Team
contact@x0tta6bl4.net
https://x0tta6bl4.net"""
    },
    {
        "company": "EFF",
        "contact": "Cindy Cohn",
        "email": "cindy@eff.org",
        "subject": "Uncensorable Mesh for EFF Activists",
        "body": """Hi Cindy,

EFF fights surveillance and censorship. I built x0tta6bl4 — a PQC self-healing mesh network 
that gives activists blackout-proof communications, even during internet shutdowns.

Key features:
- Traffic obfuscation (looks like HTTPS)
- Self-healing (survives node failures, MTTR <3 minutes)
- Post-quantum crypto (NIST FIPS 203/204)
- DAO governance (decentralized control)

I'd love to show you how it works. 15-minute demo?

Best,
x0tta6bl4 Team
contact@x0tta6bl4.net
https://x0tta6bl4.net"""
    },
    {
        "company": "Mullvad VPN",
        "contact": "Jan Jonsson",
        "email": "jan@mullvad.net",
        "subject": "Quantum-Safe Tunnel Mesh for Mullvad",
        "body": """Hi Jan,

Mullvad leads privacy with no-logs VPN. As WireGuard quantum vulnerability discussions continue, 
I built x0tta6bl4 — a quantum-safe mesh network with NIST-standard post-quantum cryptography.

Key benefits:
- ML-KEM-768 encryption (NIST FIPS 203)
- Self-healing architecture (MTTR <3 minutes)
- Mesh networking (no single point of failure)

Interested in a demo?

Best,
x0tta6bl4 Team
contact@x0tta6bl4.net
https://x0tta6bl4.net"""
    },
    {
        "company": "Access Now",
        "contact": "Brett Solomon",
        "email": "brett@accessnow.org",
        "subject": "Unblockable Mesh for #KeepItOn Campaign",
        "body": """Hi Brett,

Access Now fights internet shutdowns in 50+ countries (#KeepItOn). I built x0tta6bl4 — 
a mesh network that's impossible to block, even during blackouts.

Key features:
- Traffic obfuscation (looks like HTTPS)
- Self-healing (survives node failures)
- Post-quantum crypto (future-proof)
- Works even when ISPs are blocked

I'd love to show you how it works. 15-minute demo?

Best,
x0tta6bl4 Team
contact@x0tta6bl4.net
https://x0tta6bl4.net"""
    },
    {
        "company": "Signal Foundation",
        "contact": "Meredith Whittaker",
        "email": "meredith@signal.org",
        "subject": "Self-Healing Mesh Backend for Signal",
        "body": """Hi Meredith,

Signal sets the privacy standard for 100M+ users. As you explore mesh extensions and PQC migration, 
I built x0tta6bl4 — a self-healing mesh network with NIST-standard post-quantum cryptography.

Key benefits:
- ML-KEM-768 encryption (NIST FIPS 203)
- Self-healing architecture (MTTR <3 minutes)
- Mesh networking (decentralized backend)
- DAO governance (community control)

Would you be open to a 15-minute demo call?

Best,
x0tta6bl4 Team
contact@x0tta6bl4.net
https://x0tta6bl4.net"""
    }
]


def get_gmail_service():
    """Аутентификация и получение сервиса Gmail API"""
    creds = None
    # Файл token.json хранит токены доступа и обновления
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # Если нет валидных credentials, запускаем OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("❌ Ошибка: credentials.json не найден!")
                print("Пожалуйста, скачайте credentials.json из Google Cloud Console:")
                print("https://console.cloud.google.com/apis/credentials")
                return None
            
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Сохраняем credentials для будущих запусков
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    return build('gmail', 'v1', credentials=creds)


def create_message(sender, to, subject, body, bcc=None):
    """Создание MIME сообщения"""
    message = MIMEText(body, 'plain', 'utf-8')
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    if bcc:
        message['bcc'] = bcc
    
    return {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}


def send_email(service, sender, email_config, bcc=None, dry_run=True):
    """Отправка email через Gmail API"""
    try:
        message = create_message(
            sender,
            email_config['email'],
            email_config['subject'],
            email_config['body'],
            bcc
        )
        
        if dry_run:
            print(f"\n📧 [DRY RUN] Email для {email_config['company']} ({email_config['contact']}):")
            print(f"   To: {email_config['email']}")
            print(f"   Subject: {email_config['subject']}")
            print(f"   Body length: {len(email_config['body'])} chars")
            return True
        else:
            sent = service.users().messages().send(userId='me', body=message).execute()
            print(f"✅ Email отправлен: {email_config['company']} - ID: {sent['id']}")
            return True
            
    except Exception as e:
        print(f"❌ Ошибка отправки для {email_config['company']}: {str(e)}")
        return False


def update_crm_csv(company, status, date_sent=None):
    """Обновление CRM CSV файла"""
    csv_file = 'crm_outreach_tracking.csv'
    
    # Читаем существующие данные
    rows = []
    with open(csv_file, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            if row['Company'] == company:
                row['Status'] = status
                if date_sent:
                    row['Date Sent'] = date_sent
            rows.append(row)
    
    # Записываем обновленные данные
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    """Главная функция"""
    print("=" * 60)
    print("📧 Outreach Email Sender для ТОП-5 Компаний")
    print("=" * 60)
    
    # Проверяем режим работы
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--send':
        dry_run = False
        print("\n⚠️  Реальная отправка emails!")
    else:
        dry_run = True
        print("\n📧 Тестовый режим (dry run). Для реальной отправки используйте: python3 send_outreach_emails.py --send")
    
    if not dry_run:
        print("\n⚠️  Реальная отправка emails!")
        
        # Получаем сервис Gmail
        service = get_gmail_service()
        if not service:
            return
        
        # Получаем email отправителя
        profile = service.users().getProfile(userId='me').execute()
        sender_email = profile['emailAddress']
        print(f"\nОтправитель: {sender_email}")
    else:
        service = None
        sender_email = "your-email@gmail.com"
    
    # BCC для отслеживания
    import sys
    bcc_email = None
    if len(sys.argv) > 2:
        bcc_email = sys.argv[2]
    
    print("\n" + "=" * 60)
    print(f"📋 Отправка {len(EMAILS_CONFIG)} emails...")
    print("=" * 60)
    
    # Отправляем emails
    sent_count = 0
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    for idx, email_config in enumerate(EMAILS_CONFIG, 1):
        print(f"\n{idx}. {email_config['company']} ({email_config['contact']})")
        
        if send_email(service, sender_email, email_config, bcc_email, dry_run):
            sent_count += 1
            if not dry_run:
                update_crm_csv(email_config['company'], 'Sent', current_date)
    
    print("\n" + "=" * 60)
    if dry_run:
        print(f"✅ Тестовый режим завершен. {sent_count}/{len(EMAILS_CONFIG)} emails готовы к отправке.")
        print("\nДля реальной отправки запустите снова и выберите 'n' на вопрос о dry run.")
    else:
        print(f"✅ Отправлено {sent_count}/{len(EMAILS_CONFIG)} emails")
        print(f"📊 CRM обновлен: crm_outreach_tracking.csv")
    print("=" * 60)
    
    # Показываем follow-up даты
    print("\n📅 Follow-up напоминания:")
    followup_date = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
    for email_config in EMAILS_CONFIG:
        print(f"   - {email_config['company']}: {followup_date}")


if __name__ == '__main__':
    main()
