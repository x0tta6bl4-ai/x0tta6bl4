# Operational Security Protocols

## Overview

This document outlines operational security (OPSEC) protocols for maintaining separation between real and pseudonymous identities when using the Anti-Geolocation System.

## Identity Compartmentalization

### Real Identity (RI)
- Used for: Personal banking, government services, medical records, legal documents
- Device: Primary personal device
- Network: Home ISP (no VPN)
- Browser: Standard configuration
- Accounts: Personal email, social media with real name

### Pseudonymous Identity A (PI-A)
- Used for: Professional activities, public communications
- Device: Dedicated VM or separate hardware
- Network: VPN chain through specific country
- Browser: Hardened Firefox with specific fingerprint
- Accounts: Professional email, LinkedIn, GitHub

### Pseudonymous Identity B (PI-B)
- Used for: Research, sensitive investigations
- Device: Tails USB or disposable VM
- Network: Tor only
- Browser: Tor Browser
- Accounts: ProtonMail, Signal

### Pseudonymous Identity C (PI-C)
- Used for: Online purchases, subscriptions
- Device: Containerized browser
- Network: VPN through commercial-friendly country
- Browser: Hardened Chrome
- Accounts: Dedicated email, payment methods

## Separation Protocols

### Physical Separation
1. **Hardware Separation**
   - Use separate physical devices for different identities when possible
   - If using one device: Use Qubes OS with strict VM isolation
   - Never mix USB devices between identities

2. **Network Separation**
   - Different VPN endpoints for different identities
   - Never connect multiple identities simultaneously
   - Use different WiFi networks when possible

3. **Temporal Separation**
   - Schedule identity switches with time gaps
   - Clear all caches and restart between switches
   - Avoid rapid switching between identities

### Digital Separation

#### Browser Isolation
```bash
# Identity A
identity-manager activate identity-a
firefox -P identity-a &

# When done
pkill -f firefox
identity-manager deactivate identity-a

# Wait before switching
sleep 300  # 5 minutes

# Identity B
identity-manager activate identity-b
chromium-hardened &
```

#### File System Isolation
- Each identity has its own encrypted volume
- Never share files between identities without sanitization
- Use `wipe` or `shred` for secure deletion

#### Clipboard Isolation
- Disable clipboard sharing between VMs
- Clear clipboard after sensitive operations: `echo -n | xclip -selection clipboard`

## Behavioral Patterns

### Typing Patterns
- Vary typing speed and error rate between identities
- Use different keyboard layouts if multilingual
- Avoid biometric authentication (Windows Hello, Touch ID)

### Mouse Patterns
- Use different mouse sensitivity settings
- Vary scroll speed and patterns
- Consider using touchpad vs mouse for different identities

### Time Patterns
- Match timezone to claimed location
- Vary active hours to match claimed profession/lifestyle
- Avoid 24/7 activity patterns

### Language Patterns
- Use different vocabulary and writing styles
- Vary formality levels
- Match language proficiency to claimed background

## Communication Security

### Email
1. **Use different providers per identity**
   - RI: Gmail/Outlook
   - PI-A: ProtonMail
   - PI-B: Tutanota
   - PI-C: Disroot

2. **Email Headers**
   - Check that VPN IP doesn't appear in headers
   - Use providers that strip identifying headers
   - Test with: https://mxtoolbox.com/emailheaders.aspx

### Messaging
- Signal: Primary for encrypted communication
- Wire: Secondary option
- Session: For maximum anonymity
- Never use the same phone number across identities

### Voice/Video
- Use voice modulation if necessary
- Different backgrounds/virtual backgrounds
- Vary camera angles and lighting

## Payment Security

### Payment Methods
1. **Cryptocurrency**
   - Use Monero for maximum privacy
   - Bitcoin only through CoinJoin
   - Never reuse addresses

2. **Prepaid Cards**
   - Purchase with cash
   - Different providers per identity
   - Register with identity-appropriate details

3. **Virtual Cards**
   - Privacy.com or similar
   - Different cards per merchant
   - Match billing address to identity location

### Financial Separation
- Never transfer between identity accounts
- Use different exchanges for crypto
- Vary transaction patterns and amounts

## Travel and Location

### Digital Location
- Match VPN location to claimed timezone
- Use location-appropriate language settings
- Consider local holidays and business hours

### Physical Location
- If traveling, maintain digital location consistency
- Be aware of CCTV and facial recognition
- Use different travel patterns per identity

## Incident Response

### Suspected Compromise

#### Level 1: Suspicious Activity
1. Document suspicious indicators
2. Change passwords for affected identity
3. Rotate VPN endpoints
4. Review recent activity logs
5. Continue monitoring

#### Level 2: Probable Compromise
1. Immediately disconnect all network interfaces
2. Terminate all active sessions
3. Force logout all accounts
4. Revoke OAuth tokens
5. Rotate all credentials
6. Switch to backup identity infrastructure
7. Analyze attack vector

#### Level 3: Confirmed Compromise
1. Complete identity severance protocol
2. Assume all traffic analyzed
3. Notify contacts via out-of-band channel
4. Establish new identity from scratch
5. Review and improve OPSEC procedures

### Emergency Identity Severance Protocol

```bash
#!/bin/bash
# Emergency Identity Severance
# Run this script if identity is compromised

echo "EMERGENCY IDENTITY SEVERANCE"
echo "============================"

# 1. Network disconnect
echo "[1/7] Disconnecting network..."
nmcli networking off 2>/dev/null || true
systemctl stop NetworkManager 2>/dev/null || true
ip link set down eth0 2>/dev/null || true
ip link set down wlan0 2>/dev/null || true

# 2. Kill all browsers
echo "[2/7] Killing browser processes..."
pkill -9 -f firefox
pkill -9 -f chrome
pkill -9 -f chromium

# 3. Kill VPN
echo "[3/7] Stopping VPN..."
pkill -9 -f openvpn
wg-quick down all 2>/dev/null || true
systemctl stop vpn-chain 2>/dev/null || true

# 4. Activate killswitch
echo "[4/7] Activating killswitch..."
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT DROP
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# 5. Clear sensitive data
echo "[5/7] Clearing sensitive data..."
shred -vfz -n 3 ~/.bash_history 2>/dev/null || true
shred -vfz -n 3 ~/.zsh_history 2>/dev/null || true
history -c 2>/dev/null || true

# 6. Wipe memory (if possible)
echo "[6/7] Attempting memory wipe..."
echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true

# 7. Log the event
echo "[7/7] Logging event..."
echo "$(date): Emergency severance executed" >> /var/log/emergency-severance.log

echo ""
echo "EMERGENCY SEVERANCE COMPLETE"
echo "System is now isolated. Assess situation before reconnecting."
```

## Verification Checklist

### Daily Checks
- [ ] VPN connection active and correct location
- [ ] No IP/DNS leaks (check ipleak.net)
- [ ] Correct browser profile loaded
- [ ] Timezone matches claimed location
- [ ] No accidental account logins

### Weekly Checks
- [ ] Rotate MAC addresses
- [ ] Review leak detector logs
- [ ] Check for browser fingerprint changes
- [ ] Verify identity isolation
- [ ] Update security software

### Monthly Checks
- [ ] Full system verification (`verify.sh`)
- [ ] Review and rotate VPN endpoints
- [ ] Audit account access logs
- [ ] Update emergency protocols
- [ ] Practice identity switch procedures

## Common Mistakes to Avoid

### Technical Mistakes
1. **DNS Leaks**: Always verify DNS is going through VPN
2. **WebRTC Leaks**: Keep WebRTC disabled in browsers
3. **Time Drift**: Ensure system time matches VPN location
4. **Geolocation APIs**: Deny all location requests
5. **Browser Extensions**: Review permissions regularly

### Behavioral Mistakes
1. **Writing Style**: Maintain consistent voice per identity
2. **Knowledge Leakage**: Don't reference information from other identities
3. **Timing**: Don't be active on multiple identities simultaneously
4. **Cross-posting**: Never share content between identities
5. **Friend Networks**: Keep social circles separate

### Operational Mistakes
1. **Hardware Sharing**: Don't use same devices without sanitization
2. **Payment Trails**: Keep financial transactions separate
3. **Emergency Contacts**: Don't use same recovery options
4. **Backup Locations**: Don't use same cloud storage
5. **Communication**: Don't mention other identities

## Advanced Techniques

### Plausible Deniability
- Maintain a "decoy" identity with weaker OPSEC
- Use it for activities that might attract attention
- Keep real sensitive identities completely separate

### Cover Stories
- Develop consistent backstories for each identity
- Practice telling them until natural
- Keep details minimal but consistent
- Avoid unnecessary specifics

### Disinformation
- Intentionally leak false information in decoy identity
- Create digital trails pointing to wrong locations
- Use disinformation to confuse correlation attempts

## Training Exercises

### Monthly Drill
1. Time identity switch procedure
2. Practice emergency severance
3. Verify all backups work
4. Test alert channels
5. Review and update protocols

### Quarterly Review
1. Full system audit
2. Threat model update
3. Tool evaluation
4. OPSEC procedure review
5. Incident response test

## Resources

### Tools
- [EFF Surveillance Self-Defense](https://ssd.eff.org/)
- [Security in a Box](https://securityinabox.org/)
- [Qubes OS Documentation](https://www.qubes-os.org/doc/)

### Reading
- "The Art of Invisibility" by Kevin Mitnick
- "Extreme Privacy" by Michael Bazzell
- EFF's "Surveillance Self-Defense" guide

### Communities
- r/opsec (Reddit)
- r/privacy (Reddit)
- PrivacyTools.io community

## Conclusion

Operational security is an ongoing process, not a one-time setup. Regular review, practice, and adaptation to new threats are essential for maintaining effective separation between identities.

Remember: The strongest technical protections can be undermined by a single operational mistake. Stay vigilant, stay paranoid, stay safe.
