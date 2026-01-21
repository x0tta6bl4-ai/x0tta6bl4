/**
 * @type import('hardhat/config').HardhatUserConfig
 * Hardhat configuration for x0tta6bl4 DAO smart contracts
 * Networks: Polygon Mumbai testnet, Ethereum Sepolia, local Hardhat
 * Version: 1.0.0
 */

require('@nomicfoundation/hardhat-toolbox');
require('@openzeppelin/hardhat-upgrades');
require('hardhat-gas-reporter');
require('solidity-coverage');
require('dotenv').config();

const POLYGON_MUMBAI_RPC = process.env.POLYGON_MUMBAI_RPC || 'https://rpc-mumbai.maticvigil.com';
const ETHEREUM_SEPOLIA_RPC = process.env.ETHEREUM_SEPOLIA_RPC || 'https://sepolia.infura.io/v3/YOUR_INFURA_KEY';
const PRIVATE_KEY = process.env.PRIVATE_KEY || '0x0000000000000000000000000000000000000000000000000000000000000000';
const POLYGONSCAN_API_KEY = process.env.POLYGONSCAN_API_KEY || '';

module.exports = {
  solidity: {
    version: '0.8.9',
    settings: {
      optimizer: {
        enabled: true,
        runs: 200,
      },
    },
  },

  networks: {
    hardhat: {
      chainId: 31337,
      forking: {
        enabled: process.env.FORKING === 'true',
        url: POLYGON_MUMBAI_RPC,
      },
      allowUnlimitedContractSize: true,
    },

    // Polygon Mumbai Testnet (recommended for DAO testing)
    mumbai: {
      url: POLYGON_MUMBAI_RPC,
      accounts: [PRIVATE_KEY],
      chainId: 80001,
      gasPrice: 'auto',
      timeout: 40000,
    },

    // Ethereum Sepolia Testnet
    sepolia: {
      url: ETHEREUM_SEPOLIA_RPC,
      accounts: [PRIVATE_KEY],
      chainId: 11155111,
      gasPrice: 'auto',
      timeout: 40000,
    },

    // Polygon Mainnet (production)
    polygon: {
      url: process.env.POLYGON_MAINNET_RPC || 'https://polygon-rpc.com/',
      accounts: [PRIVATE_KEY],
      chainId: 137,
      gasPrice: 'auto',
      timeout: 40000,
    },
  },

  gasReporter: {
    enabled: process.env.REPORT_GAS === 'true',
    currency: 'USD',
    coinmarketcap: process.env.COINMARKETCAP_API_KEY,
    outputFile: 'gas-report.txt',
    noColors: true,
  },

  etherscan: {
    apiKey: {
      polygon: POLYGONSCAN_API_KEY,
      polygonMumbai: POLYGONSCAN_API_KEY,
      sepolia: process.env.ETHERSCAN_API_KEY || '',
    },
  },

  paths: {
    sources: './src/dao/contracts',
    tests: './tests/hardhat',
    cache: './cache',
    artifacts: './artifacts',
  },

  mocha: {
    timeout: 40000,
  },
};
