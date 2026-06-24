Current Distribution Policy

Only VLESS Reality on TCP port 443 is currently considered distributable.

For Reality profiles, the SNI value must come from the live server config:
`/usr/local/etc/xray/config.json`
`inbounds[].streamSettings.realitySettings.serverNames[0]`.
Do not hard-code a different masking domain into client templates.

Do not issue client profiles for 8443, 9443, 8388, or 8080 until
scripts/validate-installation.sh reports external reachability for that public
port and, for TLS profiles, confirms that the public endpoint reaches the local
Xray certificate instead of another TLS service.

Quarantined examples live under clients/quarantine-unverified/. They are kept
for reference only and are not production client profiles.
