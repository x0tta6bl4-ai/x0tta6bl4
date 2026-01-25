
/* eslint-disable no-restricted-globals */

const KERF = 3; // 3mm Saw Blade Width

self.onmessage = (e) => {
    const { parts, sheetW, sheetH, trim, materialsConfig } = e.data;

    // Group by Material
    const partsByMat = {};
    parts.forEach(p => {
        if (!partsByMat[p.materialId]) partsByMat[p.materialId] = [];
        partsByMat[p.materialId].push(p);
    });

    const results = {};

    Object.keys(partsByMat).forEach(matId => {
        const matParts = partsByMat[matId];
        const config = materialsConfig[matId] || { isTextureStrict: false };
        results[matId] = optimizeMaterialGroup(matParts, sheetW, sheetH, trim, config.isTextureStrict, matId);
    });

    self.postMessage(results);
};

function optimizeMaterialGroup(parts, sheetW, sheetH, trim, isTextureStrict, activeMatId) {
    if (!parts || parts.length === 0) return [];

    // Strategies to try
    const strategies = [
        { name: 'Area', sort: (a, b) => (b.w * b.h) - (a.w * a.h) }, 
        { name: 'LongSide', sort: (a, b) => Math.max(b.w, b.h) - Math.max(a.w, a.h) }
    ];

    let bestSolution = null;
    let minSheets = Infinity;
    let minWaste = Infinity;

    for(let strat of strategies) {
        const sortedParts = parts.map(p => ({...p, placed: false}));
        sortedParts.sort(strat.sort);

        const sheets = [];
        let allPlaced = true;
        let watchdog = 0;

        while (sortedParts.some(p => !p.placed)) {
            watchdog++;
            if (watchdog > 500) { allPlaced = false; break; }

            const sheetResult = packSingleSheet(sortedParts, sheetW, sheetH, trim, isTextureStrict, activeMatId);
            
            if (sheetResult.parts.length === 0 && sortedParts.some(p => !p.placed)) {
                 break;
            }

            const usedArea = sheetResult.parts.reduce((acc, p) => acc + (p.w * p.h), 0);
            const totalArea = sheetW * sheetH;
            const waste = 100 - (usedArea / totalArea * 100);
            
            sheets.push({ ...sheetResult, waste });
        }

        if (allPlaced) {
            const avgWaste = sheets.reduce((acc, s) => acc + s.waste, 0) / sheets.length;
            if (sheets.length < minSheets || (sheets.length === minSheets && avgWaste < minWaste)) {
                minSheets = sheets.length;
                minWaste = avgWaste;
                bestSolution = sheets;
            }
        }
    }

    return bestSolution || [];
}

function packSingleSheet(partsList, sheetW, sheetH, trim, isTextureStrict, activeMatId) {
    const sheetParts = [];
    let freeRects = [{ 
        x: trim, y: trim, 
        w: sheetW - (trim * 2), 
        h: sheetH - (trim * 2) 
    }];

    const findBestFit = (partW, partH, allowRotate) => {
        let bestRectIdx = -1;
        let bestScore = Number.MAX_VALUE;
        let rotated = false;

        for (let i = 0; i < freeRects.length; i++) {
            const r = freeRects[i];
            
            // Normal
            if (r.w >= partW && r.h >= partH) {
                const score = Math.min(r.w - partW, r.h - partH);
                if (score < bestScore) {
                    bestScore = score;
                    bestRectIdx = i;
                    rotated = false;
                }
            }

            // Rotated
            if (allowRotate && r.w >= partH && r.h >= partW) {
                const score = Math.min(r.w - partH, r.h - partW);
                if (score < bestScore) {
                    bestScore = score;
                    bestRectIdx = i;
                    rotated = true;
                }
            }
        }
        return { index: bestRectIdx, rotated };
    };

    const splitFreeRect = (rectIdx, usedW, usedH) => {
        const r = freeRects[rectIdx];
        freeRects.splice(rectIdx, 1);

        const wRem = r.w - usedW;
        const hRem = r.h - usedH;
        
        if (wRem > hRem) {
             if (hRem > 0) freeRects.push({ x: r.x, y: r.y + usedH + KERF, w: r.w, h: hRem - KERF });
             if (wRem > 0) freeRects.push({ x: r.x + usedW + KERF, y: r.y, w: wRem - KERF, h: usedH });
        } else {
             if (wRem > 0) freeRects.push({ x: r.x + usedW + KERF, y: r.y, w: wRem - KERF, h: r.h });
             if (hRem > 0) freeRects.push({ x: r.x, y: r.y + usedH + KERF, w: usedW, h: hRem - KERF });
        }
    };

    for (let i = 0; i < partsList.length; i++) {
         const p = partsList[i];
         if (p.placed) continue;

         const allowRotate = !isTextureStrict; 
         const { index, rotated } = findBestFit(p.w, p.h, allowRotate);
         
         if (index !== -1) {
             const r = freeRects[index];
             const placeW = rotated ? p.h : p.w;
             const placeH = rotated ? p.w : p.h;

             sheetParts.push({
                 id: p.id, name: p.name,
                 x: r.x, y: r.y, w: placeW, h: placeH,
                 finishW: p.w, finishH: p.h,
                 rotated: rotated, materialId: activeMatId,
                 layer: p.layer
             });

             splitFreeRect(index, placeW, placeH);
             p.placed = true;
         }
    }
    
    freeRects = freeRects.filter(r => r.w > 50 && r.h > 50);
    
    return { parts: sheetParts, freeRects };
}
