/**
 * Hardhat Configuration for X0T Token
 * 
 * Networks:
 * - localhost: Local Hardhat node
 * - polygon_mumbai: Polygon testnet
 * - polygon: Polygon mainnet
 * - base_sepolia: Base testnet
 * - base: Base mainnet
 */

import "@nomicfoundation/hardhat-toolbox";
import dotenv from "dotenv";
dotenv.config();

const PRIVATE_KEY = process.env.PRIVATE_KEY || "0x0000000000000000000000000000000000000000000000000000000000000001";

/** @type import('hardhat/config').HardhatUserConfig */
export default {
    solidity: {
        version: "0.8.20",
        settings: {
            optimizer: {
                enabled: true,
                runs: 200
            }
        }
    },

    networks: {
        // Local development
        localhost: {
            url: "http://127.0.0.1:8545"
        },
        hardhat: {
            chainId: 31337
        },

        // Polygon (recommended for low fees)
        polygon_mumbai: {
            url: process.env.POLYGON_MUMBAI_RPC || "https://rpc-mumbai.maticvigil.com",
            accounts: [PRIVATE_KEY],
            chainId: 80001,
            gasPrice: 35000000000 // 35 gwei
        },
        polygon: {
            url: process.env.POLYGON_RPC || "https://polygon-rpc.com",
            accounts: [PRIVATE_KEY],
            chainId: 137,
            gasPrice: 50000000000 // 50 gwei
        },

        // Base (Coinbase L2, very low fees)
        base_sepolia: {
            url: process.env.BASE_SEPOLIA_RPC || "https://sepolia.base.org",
            accounts: [PRIVATE_KEY],
            chainId: 84532,
            gasPrice: 1000000000 // 1 gwei
        },
        base: {
            url: process.env.BASE_RPC || "https://mainnet.base.org",
            accounts: [PRIVATE_KEY],
            chainId: 8453,
            gasPrice: 1000000000 // 1 gwei
        },

        // Arbitrum (alternative L2)
        arbitrum_sepolia: {
            url: process.env.ARBITRUM_SEPOLIA_RPC || "https://sepolia-rollup.arbitrum.io/rpc",
            accounts: [PRIVATE_KEY],
            chainId: 421614
        },
        arbitrum: {
            url: process.env.ARBITRUM_RPC || "https://arb1.arbitrum.io/rpc",
            accounts: [PRIVATE_KEY],
            chainId: 42161
        }
    },

    etherscan: {
        apiKey: {
            polygon: process.env.POLYGONSCAN_API_KEY || "",
            polygonMumbai: process.env.POLYGONSCAN_API_KEY || "",
            base: process.env.BASESCAN_API_KEY || "",
            baseSepolia: process.env.BASESCAN_API_KEY || "",
            arbitrumOne: process.env.ARBISCAN_API_KEY || "",
            arbitrumSepolia: process.env.ARBISCAN_API_KEY || ""
        },
        customChains: [
            {
                network: "base",
                chainId: 8453,
                urls: {
                    apiURL: "https://api.basescan.org/api",
                    browserURL: "https://basescan.org"
                }
            },
            {
                network: "baseSepolia",
                chainId: 84532,
                urls: {
                    apiURL: "https://api-sepolia.basescan.org/api",
                    browserURL: "https://sepolia.basescan.org"
                }
            }
        ]
    },

    paths: {
        sources: "./contracts",
        tests: "./test",
        cache: "./cache",
        artifacts: "./artifacts"
    }
};
