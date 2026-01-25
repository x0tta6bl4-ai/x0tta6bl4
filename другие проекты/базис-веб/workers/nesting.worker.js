
/* eslint-disable no-restricted-globals */

// Constants required for the worker
const KERF = 4;

self.onmessage = (e) => {
    const { parts, sheetW, sheetH, trim, activeMatId } = e.data;

    if (!parts || parts.length === 0) {
        self.postMessage([]);
        return;
    }

    // Sort by largest side first (Best Fit heuristic)
    const partsToNest = [...parts];
    partsToNest.sort((a, b) => Math.max(b.w, b.h) - Math.max(a.w, a.h));

    const sheets = [];

    // GUILLOTINE PACKING ALGORITHM
    const pack = () => {
        const sheetParts = [];
        let freeRects = [{ 
            x: trim, y: trim, 
            w: sheetW - (trim * 2), 
            h: sheetH - (trim * 2) 
        }];

        const findNode = (w, h, canRotate) => {
            let bestRectIndex = -1;
            let bestScore = Number.MAX_VALUE;
            let rotated = false;

            for (let i = 0; i < freeRects.length; i++) {
                const r = freeRects[i];
                
                // Try normal orientation
                if (r.w >= w && r.h >= h) {
                    const score = Math.min(r.w - w, r.h - h);
                    if (score < bestScore) {
                        bestScore = score;
                        bestRectIndex = i;
                        rotated = false;
                    }
                }

                // Try rotated orientation
                if (canRotate && r.w >= h && r.h >= w) {
                    const score = Math.min(r.w - h, r.h - w);
                    if (score < bestScore) {
                        bestScore = score;
                        bestRectIndex = i;
                        rotated = true;
                    }
                }
            }
            return { index: bestRectIndex, rotated };
        };

        const splitRect = (freeRectIndex, w, h) => {
            const r = freeRects[freeRectIndex];
            freeRects.splice(freeRectIndex, 1);

            const wRem = r.w - w;
            const hRem = r.h - h;
            
            if (wRem > hRem) {
                 if (wRem > 0) freeRects.push({ x: r.x + w + KERF, y: r.y, w: wRem - KERF, h: r.h });
                 if (hRem > 0) freeRects.push({ x: r.x, y: r.y + h + KERF, w: w, h: hRem - KERF });
            } else {
                 if (hRem > 0) freeRects.push({ x: r.x, y: r.y + h + KERF, w: r.w, h: hRem - KERF });
                 if (wRem > 0) freeRects.push({ x: r.x + w + KERF, y: r.y, w: wRem - KERF, h: h });
            }
        };

        for (let i = 0; i < partsToNest.length; i++) {
             const p = partsToNest[i];
             if (p.placed) continue;

             const { index, rotated } = findNode(p.w, p.h, p.canRotate);
             
             if (index !== -1) {
                 const r = freeRects[index];
                 const placeW = rotated ? p.h : p.w;
                 const placeH = rotated ? p.w : p.h;

                 sheetParts.push({
                     id: p.id, name: p.name,
                     x: r.x, y: r.y, w: placeW, h: placeH,
                     finishW: p.w, finishH: p.h,
                     rotated: rotated, materialId: activeMatId
                 });

                 splitRect(index, placeW, placeH);
                 p.placed = true;
             }
        }
        return { parts: sheetParts, freeRects };
    };

    while (partsToNest.some(p => !p.placed)) {
        const result = pack();
        const usedArea = result.parts.reduce((acc, p) => acc + (p.w * p.h), 0);
        const totalArea = sheetW * sheetH;
        sheets.push({ ...result, waste: 100 - (usedArea/totalArea * 100) });
        if (sheets.length > 50) break; 
    }

    self.postMessage(sheets);
};
