import time
import requests
import subprocess
import os

WALLET_ADDRESS = "0x3De0796583c5E68EC5560555a7bB631FD10472dC"
RPC_URL = "https://sepolia.base.org"

def wait_for_funds_and_deploy():
    print(f"🕵️ Monitoring wallet: {WALLET_ADDRESS}")
    print(f"🔗 Network: Base Sepolia")
    print(f"💡 Please send testnet ETH to this address.")
    print(f"👉 Faucet: https://www.coinbase.com/faucets/base-ethereum-sepolia-faucet")
    
    while True:
        try:
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_getBalance",
                "params": [WALLET_ADDRESS, "latest"],
                "id": 1
            }
            resp = requests.post(RPC_URL, json=payload).json()
            balance_hex = resp.get("result", "0x0")
            balance_wei = int(balance_hex, 16)
            
            if balance_wei > 0:
                print(f"💰 Funds detected! Balance: {balance_wei / 10**18:.4f} ETH")
                print("🚀 Starting deployment...")
                
                # Update .env with the private key
                # (I have the PK from previous step)
                env_content = f"PRIVATE_KEY=5cc523ca4fa1ac5cab072196b488d28845b26c1e41177b652bf64ffdd4c788eb\nBASE_SEPOLIA_RPC={RPC_URL}\n"
                with open("src/dao/contracts/.env", "w") as f:
                    f.write(env_content)
                
                # Run Docker deployer
                cmd = "cd src/dao/contracts && docker run --rm --network=host --cpus=1 --memory=1g -v $(pwd):/app x0t-contracts-deployer npx hardhat run scripts/deploy_x0t.js --network base_sepolia"
                subprocess.run(cmd, shell=True)
                break
            else:
                # print(".", end="", flush=True)
                pass
        except Exception as e:
            print(f"Error checking balance: {e}")
            
        time.sleep(15)

if __name__ == "__main__":
    wait_for_funds_and_deploy()
