import { Material, TextureType } from './types';

export const MATERIAL_LIBRARY: Material[] = [
  {
    id: 'eg-w980',
    article: 'W980 SM',
    brand: 'Egger',
    name: 'Белый Платиновый',
    thickness: 16,
    pricePerM2: 1650,
    texture: TextureType.UNIFORM,
    isTextureStrict: false,
    color: '#FFFFFF',
    // Material research data (2026)
    density: 680, // kg/m³ - LDSP Egger W980
    elasticModulus: 2000, // N/mm² - typical for 16mm LDSP
    certification: 'E1', // Standard for furniture
    type: 'LDSP' // Low Density Chipboard
  },
  {
    id: 'eg-h1145',
    article: 'H1145 ST10',
    brand: 'Egger',
    name: 'Дуб Бардолино натуральный',
    thickness: 16,
    pricePerM2: 1850,
    texture: TextureType.WOOD_OAK,
    isTextureStrict: true,
    color: '#D2B48C',
    // Material research data (2026)
    density: 700, // kg/m³ - LDSP Egger H1145
    elasticModulus: 2100, // N/mm²
    certification: 'E1',
    type: 'LDSP'
  },
  {
    id: 'ks-k003',
    article: 'K003 PW',
    brand: 'Kronospan',
    name: 'Дуб Крафт Золотой',
    thickness: 16,
    pricePerM2: 1450,
    texture: TextureType.WOOD_WALNUT,
    isTextureStrict: true,
    color: '#A0522D',
    // Material research data (2026)
    density: 730, // kg/m³ - LDSP Kronospan K003
    elasticModulus: 2050, // N/mm²
    certification: 'E1',
    type: 'LDSP'
  },
  {
    id: 'ks-0191',
    article: '0191 SU',
    brand: 'Kronospan',
    name: 'Серый Графит',
    thickness: 16,
    pricePerM2: 1550,
    texture: TextureType.UNIFORM,
    isTextureStrict: false,
    color: '#333333',
    // Material research data (2026)
    density: 730, // kg/m³ - LDSP Kronospan 0191
    elasticModulus: 2050, // N/mm²
    certification: 'E1',
    type: 'LDSP'
  },
  {
    id: 'mdf-ral',
    article: 'RAL 7024',
    brand: 'MDF_RAL',
    name: 'МДФ Эмаль Матовая',
    thickness: 16, // Corrected from 18 (standard for MDF)
    pricePerM2: 2500, // Corrected from 3200 (incorrect price for 18mm)
    texture: TextureType.UNIFORM,
    isTextureStrict: false,
    color: '#374151',
    // Material research data (2026)
    density: 740, // kg/m³ - MDF standard density
    elasticModulus: 2800, // N/mm² - MDF has higher MOE than LDSP
    certification: 'E1',
    type: 'MDF' // Medium Density Fiberboard
  },
  {
    id: 'eg-hdf',
    article: 'HDF W',
    brand: 'Egger',
    name: 'ХДФ Белый (Задняя стенка)',
    thickness: 4,
    pricePerM2: 450,
    texture: TextureType.NONE,
    isTextureStrict: false,
    color: '#F0F0F0',
    // Material research data (2026)
    density: 720, // kg/m³ - HDF Egger (high-density)
    elasticModulus: 3200, // N/mm² - HDF has highest MOE
    certification: 'E1',
    type: 'HDF' // High Density Fiberboard
  }
];

export function getMaterialById(id: string): Material | undefined {
  return MATERIAL_LIBRARY.find(m => m.id === id);
}

export function getMaterialsByBrand(brand: string): Material[] {
  return MATERIAL_LIBRARY.filter(m => m.brand === brand);
}

export function getMaterialsByThickness(thickness: number): Material[] {
  return MATERIAL_LIBRARY.filter(m => m.thickness === thickness);
}
