
import { Material, TextureType } from '../types';

export const MATERIAL_LIBRARY: Material[] = [
    // --- ЛДСП (Woodgrains) ---
    { 
        id: 'eg-h1145', article: 'H1145 ST10', brand: 'Egger', name: 'Дуб Бардолино натуральный', 
        category: 'ldsp', thickness: 16, availableThicknesses: [10, 16, 25],
        pricePerM2: 1850, texture: TextureType.WOOD_OAK, isTextureStrict: true, color: '#D2B48C',
        textureUrl: '/textures/oak_bardolino.jpg', normalMapUrl: '/textures/wood_normal.jpg'
    },
    { 
        id: 'eg-h3303', article: 'H3303 ST10', brand: 'Egger', name: 'Дуб Гамильтон натуральный', 
        category: 'ldsp', thickness: 16, availableThicknesses: [16, 25],
        pricePerM2: 2100, texture: TextureType.WOOD_OAK, isTextureStrict: true, color: '#C19A6B',
        textureUrl: '/textures/oak_hamilton.jpg', normalMapUrl: '/textures/wood_normal.jpg'
    },
    { 
        id: 'eg-h1180', article: 'H1180 ST37', brand: 'Egger', name: 'Дуб Галифакс натуральный', 
        category: 'ldsp', thickness: 16, availableThicknesses: [16],
        pricePerM2: 2450, texture: TextureType.WOOD_OAK, isTextureStrict: true, color: '#A67B5B',
        normalMapUrl: '/textures/halifax_normal.jpg' // Deep embossing
    },
    { 
        id: 'ks-k003', article: 'K003 PW', brand: 'Kronospan', name: 'Дуб Крафт Золотой', 
        category: 'ldsp', thickness: 16, availableThicknesses: [16],
        pricePerM2: 1450, texture: TextureType.WOOD_WALNUT, isTextureStrict: true, color: '#A0522D'
    },
    { 
        id: 'eg-h3730', article: 'H3730 ST10', brand: 'Egger', name: 'Гикори Натуральный', 
        category: 'ldsp', thickness: 16, availableThicknesses: [16],
        pricePerM2: 1950, texture: TextureType.WOOD_ASH, isTextureStrict: true, color: '#B08D74' 
    },
    { 
        id: 'eg-h3430', article: 'H3430 ST22', brand: 'Egger', name: 'Сосна Аланд белая', 
        category: 'ldsp', thickness: 16, availableThicknesses: [16],
        pricePerM2: 1800, texture: TextureType.WOOD_ASH, isTextureStrict: true, color: '#EBE5CE' 
    },
    { 
        id: 'lm-venge', article: 'Venge', brand: 'Lamarty', name: 'Венге Мали', 
        category: 'ldsp', thickness: 16, availableThicknesses: [16, 26],
        pricePerM2: 1300, texture: TextureType.WOOD_WALNUT, isTextureStrict: true, color: '#3E2723' 
    },
    { 
        id: 'eg-h3025', article: 'H3025 ST15', brand: 'Egger', name: 'Макассар', 
        category: 'ldsp', thickness: 16, availableThicknesses: [16],
        pricePerM2: 2200, texture: TextureType.WOOD_WALNUT, isTextureStrict: true, color: '#4E342E' 
    },
    { 
        id: 'eg-h1137', article: 'H1137 ST12', brand: 'Egger', name: 'Дуб Сорано черно-коричневый', 
        category: 'ldsp', thickness: 16, availableThicknesses: [16],
        pricePerM2: 1850, texture: TextureType.WOOD_OAK, isTextureStrict: true, color: '#3B322C' 
    },
    { 
        id: 'ks-5527', article: '5527 CA', brand: 'Kronospan', name: 'Каменный Дуб', 
        category: 'ldsp', thickness: 16, availableThicknesses: [16],
        pricePerM2: 1500, texture: TextureType.WOOD_OAK, isTextureStrict: true, color: '#8D8276' 
    },

    // --- ЛДСП (Uni Colors) ---
    { 
        id: 'eg-w980', article: 'W980 SM', brand: 'Egger', name: 'Белый Платиновый', 
        category: 'ldsp', thickness: 16, availableThicknesses: [8, 10, 16, 18, 25],
        pricePerM2: 1650, texture: TextureType.UNIFORM, isTextureStrict: false, color: '#FFFFFF' 
    },
    { 
        id: 'eg-u708', article: 'U708 ST9', brand: 'Egger', name: 'Серый Светлый', 
        category: 'ldsp', thickness: 16, availableThicknesses: [16],
        pricePerM2: 1750, texture: TextureType.UNIFORM, isTextureStrict: false, color: '#C0C0C0' 
    },
    { 
        id: 'ks-0191', article: '0191 SU', brand: 'Kronospan', name: 'Серый Графит', 
        category: 'ldsp', thickness: 16, availableThicknesses: [16],
        pricePerM2: 1550, texture: TextureType.UNIFORM, isTextureStrict: false, color: '#333333' 
    },
    { 
        id: 'eg-u999', article: 'U999 ST2', brand: 'Egger', name: 'Черный', 
        category: 'ldsp', thickness: 16, availableThicknesses: [16],
        pricePerM2: 1800, texture: TextureType.UNIFORM, isTextureStrict: false, color: '#111111' 
    },
    { 
        id: 'eg-u522', article: 'U522 ST9', brand: 'Egger', name: 'Голубой Горизонт', 
        category: 'ldsp', thickness: 16, availableThicknesses: [16],
        pricePerM2: 1900, texture: TextureType.UNIFORM, isTextureStrict: false, color: '#7AA3CC' 
    },
    { 
        id: 'eg-u321', article: 'U321 ST9', brand: 'Egger', name: 'Красный Китайский', 
        category: 'ldsp', thickness: 16, availableThicknesses: [16],
        pricePerM2: 1900, texture: TextureType.UNIFORM, isTextureStrict: false, color: '#8B0000' 
    },

    // --- ЛДСП (Concrete/Material) ---
    { 
        id: 'eg-f186', article: 'F186 ST9', brand: 'Egger', name: 'Бетон Чикаго светло-серый', 
        category: 'ldsp', thickness: 16, availableThicknesses: [16],
        pricePerM2: 2100, texture: TextureType.CONCRETE, isTextureStrict: false, color: '#9E9E9E',
        normalMapUrl: '/textures/concrete_normal.jpg'
    },
    { 
        id: 'eg-f187', article: 'F187 ST9', brand: 'Egger', name: 'Бетон Чикаго темно-серый', 
        category: 'ldsp', thickness: 16, availableThicknesses: [16],
        pricePerM2: 2100, texture: TextureType.CONCRETE, isTextureStrict: false, color: '#616161',
        normalMapUrl: '/textures/concrete_normal.jpg'
    },
    { 
        id: 'eg-f206', article: 'F206 ST9', brand: 'Egger', name: 'Камень Пьетра Гриджа', 
        category: 'ldsp', thickness: 16, availableThicknesses: [16],
        pricePerM2: 2200, texture: TextureType.MARBLE, isTextureStrict: false, color: '#373737' 
    },

    // --- Массив (Solid Wood) ---
    { 
        id: 'sw-oak', article: 'SW-001', brand: 'Generic', name: 'Массив Дуба (Щит)', 
        category: 'wood', thickness: 20, availableThicknesses: [20, 40],
        pricePerM2: 8500, texture: TextureType.WOOD_OAK, isTextureStrict: true, color: '#C68E17',
        normalMapUrl: '/textures/wood_normal_sharp.jpg'
    },
    { 
        id: 'sw-pine', article: 'SW-002', brand: 'Generic', name: 'Массив Сосны (Щит)', 
        category: 'wood', thickness: 18, availableThicknesses: [18, 28],
        pricePerM2: 3200, texture: TextureType.WOOD_ASH, isTextureStrict: true, color: '#F4E4BC' 
    },
    { 
        id: 'sw-ash', article: 'SW-003', brand: 'Generic', name: 'Массив Ясеня', 
        category: 'wood', thickness: 20, availableThicknesses: [20, 40],
        pricePerM2: 7800, texture: TextureType.WOOD_ASH, isTextureStrict: true, color: '#E0C6A2' 
    },
    { 
        id: 'sw-beech', article: 'SW-004', brand: 'Generic', name: 'Массив Бука', 
        category: 'wood', thickness: 20, availableThicknesses: [20, 40],
        pricePerM2: 6500, texture: TextureType.UNIFORM, isTextureStrict: true, color: '#DEB887' 
    },

    // --- Пластик (MDF/Coating) ---
    { 
        id: 'mdf-ral-white', article: 'RAL 9003 Gloss', brand: 'MDF_RAL', name: 'Белый Глянец (Эмаль)', 
        category: 'plastic', thickness: 18, availableThicknesses: [16, 18],
        pricePerM2: 4500, texture: TextureType.UNIFORM, isTextureStrict: false, color: '#FFFFFF' 
    },
    { 
        id: 'mdf-ral-black', article: 'RAL 9005 Mat', brand: 'MDF_RAL', name: 'Черный Мат (Soft Touch)', 
        category: 'plastic', thickness: 18, availableThicknesses: [18],
        pricePerM2: 5200, texture: TextureType.UNIFORM, isTextureStrict: false, color: '#1A1A1A' 
    },
    { 
        id: 'mdf-ral-7024', article: 'RAL 7024', brand: 'MDF_RAL', name: 'МДФ Эмаль Графит', 
        category: 'plastic', thickness: 18, availableThicknesses: [18],
        pricePerM2: 3200, texture: TextureType.UNIFORM, isTextureStrict: false, color: '#374151' 
    },

    // --- Стекло ---
    { 
        id: 'gl-clear', article: 'Glass 4mm', brand: 'Generic', name: 'Стекло Прозрачное', 
        category: 'glass', thickness: 4, availableThicknesses: [4, 6],
        pricePerM2: 1200, texture: TextureType.NONE, isTextureStrict: false, color: '#E0F7FA' 
    },
    { 
        id: 'gl-mat', article: 'Satin 4mm', brand: 'Generic', name: 'Стекло Матовое (Сатин)', 
        category: 'glass', thickness: 4, availableThicknesses: [4],
        pricePerM2: 1800, texture: TextureType.UNIFORM, isTextureStrict: false, color: '#CFD8DC' 
    },
    { 
        id: 'gl-bronze', article: 'Bronze 4mm', brand: 'Generic', name: 'Стекло Бронза', 
        category: 'glass', thickness: 4, availableThicknesses: [4],
        pricePerM2: 1500, texture: TextureType.NONE, isTextureStrict: false, color: '#5D4037' 
    },

    // --- Техническое ---
    { 
        id: 'eg-hdf', article: 'HDF W', brand: 'Egger', name: 'ХДФ Белый (Задняя стенка)', 
        category: 'ldsp', thickness: 4, availableThicknesses: [3, 4],
        pricePerM2: 450, texture: TextureType.NONE, isTextureStrict: false, color: '#F0F0F0' 
    },
];
