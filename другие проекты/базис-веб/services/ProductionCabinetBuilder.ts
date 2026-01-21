import { CabinetDSL, ConstructionRule, SolvedPanel, JointTechSpec, GeometricJoint, CuttingPlan, CutDetail, SheetCutting, ValidationError, Mm, Vec3 } from '../types/ProductionArchitecture';

/**
 * Производственный строитель шкафа
 * Реализует 5-слойную архитектуру
 */
export class ProductionCabinetBuilder {
  private rules: ConstructionRule[] = [];
  private jointTechs: JointTechSpec[] = [];

  constructor() {
    this.initializeDefaultRules();
    this.initializeDefaultJointTechs();
  }

  private initializeDefaultRules(): void {
    // Правила для базовых панелей
    this.rules.push({
      id: 'rule_side_left',
      name: 'Left side panel',
      appliesTo: 'side-l',
      requires: [],
      calculate: (solved, params) => {
        const t = params.material.board.thickness;
        return {
          id: 'side-l',
          role: 'side-l',
          size: { x: t, y: params.envelope.height, z: params.envelope.depth },
          position: { x: 0, y: 0, z: 0 },
          orientation: 'X',
          edges: [
            { side: 'front', type: params.material.edge.front, length: params.envelope.height },
            { side: 'top', type: params.material.edge.top, length: params.envelope.depth },
            { side: 'bottom', type: params.material.edge.bottom, length: params.envelope.depth },
            { side: 'back', type: params.material.edge.back, length: params.envelope.height }
          ],
          holes: [],
          operationSequence: ['EDGE_BAND', 'DRILL'],
          rulesApplied: ['rule_side_left']
        };
      },
      validate: (panel) => {
        const errors: ValidationError[] = [];
        if (panel.size.y < 600) {
          errors.push({
            code: 'SIDE_TOO_SHORT',
            msg: 'Боковина < 600 мм',
            severity: 'error'
          });
        }
        if (panel.size.y > 2800) {
          errors.push({
            code: 'SIDE_TOO_TALL',
            msg: 'Боковина > 2800 мм',
            severity: 'error'
          });
        }
        return errors;
      }
    });

    this.rules.push({
      id: 'rule_side_right',
      name: 'Right side panel',
      appliesTo: 'side-r',
      requires: [],
      calculate: (solved, params) => {
        const t = params.material.board.thickness;
        return {
          id: 'side-r',
          role: 'side-r',
          size: { x: t, y: params.envelope.height, z: params.envelope.depth },
          position: { x: params.envelope.width - t, y: 0, z: 0 },
          orientation: 'X',
          edges: [
            { side: 'front', type: params.material.edge.front, length: params.envelope.height },
            { side: 'top', type: params.material.edge.top, length: params.envelope.depth },
            { side: 'bottom', type: params.material.edge.bottom, length: params.envelope.depth },
            { side: 'back', type: params.material.edge.back, length: params.envelope.height }
          ],
          holes: [],
          operationSequence: ['EDGE_BAND', 'DRILL'],
          rulesApplied: ['rule_side_right']
        };
      },
      validate: (panel) => {
        const errors: ValidationError[] = [];
        if (panel.size.y < 600) {
          errors.push({
            code: 'SIDE_TOO_SHORT',
            msg: 'Боковина < 600 мм',
            severity: 'error'
          });
        }
        if (panel.size.y > 2800) {
          errors.push({
            code: 'SIDE_TOO_TALL',
            msg: 'Боковина > 2800 мм',
            severity: 'error'
          });
        }
        return errors;
      }
    });

    this.rules.push({
      id: 'rule_top',
      name: 'Top panel',
      appliesTo: 'top',
      requires: ['side-l', 'side-r'],
      calculate: (solved, params) => {
        const t = params.material.board.thickness;
        return {
          id: 'top',
          role: 'top',
          size: { x: params.envelope.width, y: t, z: params.envelope.depth },
          position: { x: 0, y: params.envelope.height - t, z: 0 },
          orientation: 'Z',
          edges: [
            { side: 'front', type: params.material.edge.front, length: params.envelope.width },
            { side: 'left', type: params.material.edge.left, length: params.envelope.depth },
            { side: 'right', type: params.material.edge.right, length: params.envelope.depth },
            { side: 'back', type: params.material.edge.back, length: params.envelope.width }
          ],
          holes: [],
          operationSequence: ['EDGE_BAND'],
          rulesApplied: ['rule_top']
        };
      },
      validate: (panel) => {
        const errors: ValidationError[] = [];
        if (panel.size.x < 300) {
          errors.push({
            code: 'TOP_TOO_NARROW',
            msg: 'Крышка < 300 мм',
            severity: 'error'
          });
        }
        if (panel.size.x > 3000) {
          errors.push({
            code: 'TOP_TOO_WIDE',
            msg: 'Крышка > 3000 мм',
            severity: 'error'
          });
        }
        return errors;
      }
    });

    this.rules.push({
      id: 'rule_bottom',
      name: 'Bottom panel',
      appliesTo: 'bottom',
      requires: ['side-l', 'side-r'],
      calculate: (solved, params) => {
        const t = params.material.board.thickness;
        return {
          id: 'bottom',
          role: 'bottom',
          size: { x: params.envelope.width, y: t, z: params.envelope.depth },
          position: { x: 0, y: 0, z: 0 },
          orientation: 'Z',
          edges: [
            { side: 'front', type: params.material.edge.front, length: params.envelope.width },
            { side: 'left', type: params.material.edge.left, length: params.envelope.depth },
            { side: 'right', type: params.material.edge.right, length: params.envelope.depth },
            { side: 'back', type: params.material.edge.back, length: params.envelope.width }
          ],
          holes: [],
          operationSequence: ['EDGE_BAND', 'DRILL'],
          rulesApplied: ['rule_bottom']
        };
      },
      validate: (panel) => {
        const errors: ValidationError[] = [];
        if (panel.size.x < 300) {
          errors.push({
            code: 'BOTTOM_TOO_NARROW',
            msg: 'Дно < 300 мм',
            severity: 'error'
          });
        }
        if (panel.size.x > 3000) {
          errors.push({
            code: 'BOTTOM_TOO_WIDE',
            msg: 'Дно > 3000 мм',
            severity: 'error'
          });
        }
        return errors;
      }
    });

    this.rules.push({
      id: 'rule_back',
      name: 'Back panel',
      appliesTo: 'back',
      requires: ['side-l', 'side-r', 'top', 'bottom'],
      calculate: (solved, params) => {
        const t = params.material.back?.thickness || params.material.board.thickness;
        return {
          id: 'back',
          role: 'back',
          size: { x: params.envelope.width, y: params.envelope.height, z: t },
          position: { x: 0, y: 0, z: params.envelope.depth - t },
          orientation: 'Y',
          edges: [
            { side: 'front', type: 'none', length: params.envelope.width },
            { side: 'left', type: 'none', length: params.envelope.height },
            { side: 'right', type: 'none', length: params.envelope.height },
            { side: 'back', type: 'none', length: params.envelope.width }
          ],
          holes: [],
          operationSequence: ['CUT'],
          rulesApplied: ['rule_back']
        };
      },
      validate: (panel) => {
        const errors: ValidationError[] = [];
        if (panel.size.z > 10) {
          errors.push({
            code: 'BACK_TOO_THICK',
            msg: 'Спинка > 10 мм не рекомендуется',
            severity: 'warning',
            suggestion: 'Используйте HDF или DSP толщиной 3-6 мм'
          });
        }
        return errors;
      }
    });

    this.rules.push({
      id: 'rule_shelves',
      name: 'Shelves',
      appliesTo: 'shelf',
      requires: ['side-l', 'side-r'],
      calculate: (solved, params) => {
        const t = params.material.board.thickness;
        const shelfCount = params.shelves?.count || 3;
        const spacing = params.envelope.height / (shelfCount + 1);
        
        return {
          id: 'shelf',
          role: 'shelf',
          size: {
            x: params.envelope.width - 2 * t - 4,
            y: t,
            z: params.envelope.depth - t - 5
          },
          position: { x: t, y: spacing, z: t },
          orientation: 'Z',
          edges: [
            { side: 'front', type: params.material.edge.front, length: params.envelope.width - 2 * t - 4 },
            { side: 'left', type: 'none', length: params.envelope.depth - t - 5 },
            { side: 'right', type: 'none', length: params.envelope.depth - t - 5 },
            { side: 'back', type: 'none', length: params.envelope.width - 2 * t - 4 }
          ],
          holes: [],
          operationSequence: ['EDGE_BAND'],
          rulesApplied: ['rule_shelves']
        };
      },
      validate: (panel) => {
        const errors: ValidationError[] = [];
        const maxDeflection = panel.size.x / 200;
        if (maxDeflection > 15) {
          errors.push({
            code: 'SHELF_WILL_SAG',
            msg: `Полка провиснет ${maxDeflection.toFixed(1)} мм (лимит 15 мм)`,
            severity: 'warning',
            suggestion: 'Добавить ребро жёсткости'
          });
        }
        return errors;
      }
    });
  }

  private initializeDefaultJointTechs(): void {
    this.jointTechs.push({
      id: 'joint_side_bottom',
      type: 'tee',
      panelA: 'side-l',
      panelB: 'bottom',
      fastener: {
        type: 'confirmat_7x50',
        quantity: 2,
        spacing: 600,
        minDistFromEdge: 50
      },
      drillPattern: {
        direction: 'into_panelB',
        holes: [
          { id: 'drill_1', position: { x: 50, y: 0, z: 50 }, diameter: 5 as Mm, depth: 45 as Mm, tool: 'DRILL_5_HSS', feedrate: 300, spindle: 2000 },
          { id: 'drill_2', position: { x: 50, y: 0, z: 650 }, diameter: 5 as Mm, depth: 45 as Mm, tool: 'DRILL_5_HSS', feedrate: 300, spindle: 2000 }
        ]
      }
    });
  }

  async build(dsl: CabinetDSL): Promise<ProductionCabinetModel> {
    const solved = new Map<string, SolvedPanel>();
    const errors: ValidationError[] = [];
    const warnings: ValidationError[] = [];

    // Применение правил
    for (const rule of this.rules) {
      try {
        const panelData = rule.calculate(solved, dsl);
        const panel: SolvedPanel = {
          ...panelData,
          rulesApplied: [rule.id]
        } as SolvedPanel;

        const ruleErrors = rule.validate(panel);
        ruleErrors.forEach(e => {
          if (e.severity === 'error') {
            errors.push(e);
          } else {
            warnings.push(e);
          }
        });

        if (ruleErrors.some(e => e.severity === 'error')) {
          continue;
        }

        solved.set(panel.id, panel);
      } catch (e) {
        errors.push({
          code: 'RULE_FAILED',
          msg: `Правило ${rule.id} не применилось: ${e}`,
          severity: 'error'
        });
      }
    }

    if (errors.length > 0) {
      throw new Error('Критические ошибки при сборке');
    }

    const joints = this.detectJoints(solved, dsl);
    const appliedJoints: JointTechSpec[] = [];
    
    joints.forEach(geomJoint => {
      const techSpec = this.findTechSpec(geomJoint, dsl);
      appliedJoints.push(techSpec);

      const targetPanel = solved.get(techSpec.panelB)!;
      targetPanel.holes = targetPanel.holes || [];
      targetPanel.holes.push(...techSpec.drillPattern.holes);
    });

    const cutDetails = this.generateCutDetails(solved, dsl);
    const cuttingPlan = await this.optimizeCutting(cutDetails, dsl);

    return {
      dsl,
      solved,
      joints: appliedJoints,
      cutting: cuttingPlan,
      validation: { errors, warnings },
      export: {
        toDXF: () => this.exportToDXF(solved, appliedJoints),
        toJSON: () => this.exportToJSON(solved),
        toPDF: () => this.exportToPDF(solved, appliedJoints),
        toGCode: () => this.exportToGCode(solved, appliedJoints)
      }
    };
  }

  private detectJoints(solved: Map<string, SolvedPanel>, dsl: CabinetDSL): GeometricJoint[] {
    const joints: GeometricJoint[] = [];
    const panels = Array.from(solved.values());

    for (let i = 0; i < panels.length; i++) {
      for (let j = i + 1; j < panels.length; j++) {
        const pA = panels[i];
        const pB = panels[j];
        if (this.aabbsIntersect(this.getPanelAABB(pA), this.getPanelAABB(pB))) {
          joints.push({
            panelA: pA.id,
            panelB: pB.id,
            type: this.determineJointType(pA, pB),
            length: this.calculateJointLength(pA, pB)
          });
        }
      }
    }

    return joints;
  }

  private findTechSpec(geomJoint: GeometricJoint, dsl: CabinetDSL): JointTechSpec {
    const key = `${geomJoint.panelA}_${geomJoint.panelB}_${geomJoint.type}`;
    let spec = this.jointTechs.find(j => 
      j.panelA === geomJoint.panelA && 
      j.panelB === geomJoint.panelB &&
      j.type === geomJoint.type
    );

    if (!spec) {
      spec = this.generateDefaultJointSpec(geomJoint, dsl);
    }

    spec.fastener.quantity = Math.max(
      2,
      Math.floor(geomJoint.length / spec.fastener.spacing)
    );

    return spec;
  }

  private generateDefaultJointSpec(geomJoint: GeometricJoint, dsl: CabinetDSL): JointTechSpec {
    return {
      id: `joint_${geomJoint.panelA}_${geomJoint.panelB}`,
      type: geomJoint.type as any,
      panelA: geomJoint.panelA,
      panelB: geomJoint.panelB,
      fastener: {
        type: dsl.constraints?.jointType === 'confirmat' ? 'confirmat_7x50' : 'dowel_8x30',
        quantity: 2,
        spacing: 600,
        minDistFromEdge: 50
      },
      drillPattern: {
        direction: 'into_panelB',
        holes: [
          { id: 'drill_1', position: { x: 50, y: 0, z: 50 }, diameter: 5 as Mm, depth: 45 as Mm, tool: 'DRILL_5_HSS', feedrate: 300, spindle: 2000 },
          { id: 'drill_2', position: { x: 50, y: 0, z: 650 }, diameter: 5 as Mm, depth: 45 as Mm, tool: 'DRILL_5_HSS', feedrate: 300, spindle: 2000 }
        ]
      }
    };
  }

  private generateCutDetails(solved: Map<string, SolvedPanel>, dsl: CabinetDSL): CutDetail[] {
    const details: CutDetail[] = [];

    solved.forEach(panel => {
      details.push({
        id: panel.id,
        size: panel.size,
        grain: panel.role === 'side-l' || panel.role === 'side-r' ? 'vertical' : 'horizontal',
        edgeProtectedSides: panel.edges.filter(e => e.type !== 'none').map(e => e.side),
        priority: panel.role === 'top' || panel.role === 'bottom' ? 1 : 2,
        operations: {
          edgeBanding: panel.edges,
          drilling: panel.holes
        }
      });
    });

    return details;
  }

  private async optimizeCutting(details: CutDetail[], dsl: CabinetDSL): Promise<CuttingPlan> {
    const sorted = [...details].sort((a, b) => {
      if (a.priority !== b.priority) return a.priority - b.priority;
      return (b.size.x * b.size.z) - (a.size.x * a.size.z);
    });

    const sheets: SheetCutting[] = [];
    let currentSheet = this.createEmptySheet(dsl.material.board);

    for (const detail of sorted) {
      const placed = this.placeDetailWithEdgeProtection(currentSheet, detail);
      if (!placed) {
        sheets.push(currentSheet);
        currentSheet = this.createEmptySheet(dsl.material.board);
        this.placeDetailWithEdgeProtection(currentSheet, detail);
      }
    }

    sheets.push(currentSheet);

    const totalDetailArea = sorted.reduce((sum, d) => sum + d.size.x * d.size.z, 0);
    const totalSheetArea = sheets.length * (2800 * 1850);
    const KIM = (totalDetailArea / totalSheetArea) * 100;

    return {
      sheets,
      metrics: {
        totalSheets: sheets.length,
        KIM,
        totalWaste: totalSheetArea - totalDetailArea,
        estimatedCuttingTime: sheets.length * 30
      }
    };
  }

  private createEmptySheet(material: any): SheetCutting {
    return {
      sheetNumber: 0,
      material,
      details: [],
      metrics: { usedArea: 0, wasteArea: 0, utilizationRatio: 0 }
    };
  }

  private placeDetailWithEdgeProtection(sheet: SheetCutting, detail: CutDetail): boolean {
    const position = { x: 0, y: 0 };
    sheet.details.push({
      ...detail,
      size: detail.size
    });
    return true;
  }

  private getPanelAABB(panel: SolvedPanel): { min: Vec3; max: Vec3 } {
    return {
      min: {
        x: panel.position.x,
        y: panel.position.y,
        z: panel.position.z
      },
      max: {
        x: panel.position.x + panel.size.x,
        y: panel.position.y + panel.size.y,
        z: panel.position.z + panel.size.z
      }
    };
  }

  private aabbsIntersect(a: { min: Vec3; max: Vec3 }, b: { min: Vec3; max: Vec3 }): boolean {
    return a.min.x < b.max.x && a.max.x > b.min.x &&
           a.min.y < b.max.y && a.max.y > b.min.y &&
           a.min.z < b.max.z && a.max.z > b.min.z;
  }

  private determineJointType(pA: SolvedPanel, pB: SolvedPanel): string {
    const aabbA = this.getPanelAABB(pA);
    const aabbB = this.getPanelAABB(pB);

    const overlapX = Math.min(aabbA.max.x, aabbB.max.x) - Math.max(aabbA.min.x, aabbB.min.x);
    const overlapY = Math.min(aabbA.max.y, aabbB.max.y) - Math.max(aabbA.min.y, aabbB.min.y);
    const overlapZ = Math.min(aabbA.max.z, aabbB.max.z) - Math.max(aabbA.min.z, aabbB.min.z);

    const maxOverlap = Math.max(overlapX, overlapY, overlapZ);
    
    if (maxOverlap === overlapX) return 'overlap';
    if (maxOverlap === overlapY) return 'tee';
    return 'corner';
  }

  private calculateJointLength(pA: SolvedPanel, pB: SolvedPanel): Mm {
    const aabbA = this.getPanelAABB(pA);
    const aabbB = this.getPanelAABB(pB);

    const overlapX = Math.min(aabbA.max.x, aabbB.max.x) - Math.max(aabbA.min.x, aabbB.min.x);
    const overlapY = Math.min(aabbA.max.y, aabbB.max.y) - Math.max(aabbA.min.y, aabbB.min.y);
    const overlapZ = Math.min(aabbA.max.z, aabbB.max.z) - Math.max(aabbA.min.z, aabbB.min.z);

    return Math.max(overlapX, overlapY, overlapZ) as Mm;
  }

  private exportToDXF(solved: Map<string, SolvedPanel>, joints: JointTechSpec[]): string {
    let dxf = '999\nБазис-Веб CAM\n';
    dxf += '0\nSECTION\n2\nHEADER\n9\n$ACADVER\n1\nAC1027\n0\nENDSEC\n';
    
    dxf += '0\nSECTION\n2\nTABLES\n0\nTABLE\n2\nLAYER\n70\n3\n';
    dxf += '0\nLAYER\n2\nCUT\n70\n0\n62\n7\n6\nCONTINUOUS\n';
    dxf += '0\nLAYER\n2\nDRILL_5x45\n70\n0\n62\n1\n6\nCONTINUOUS\n';
    dxf += '0\nLAYER\n2\nEDGE_BAND\n70\n0\n62\n2\n6\nCONTINUOUS\n';
    dxf += '0\nENDTAB\n0\nENDTAB\n0\nENDSEC\n';
    
    dxf += '0\nSECTION\n2\nENTITIES\n';
    solved.forEach(panel => {
      dxf += '0\nLWPOLYLINE\n8\nCUT\n70\n1\n90\n4\n';
      const corners = [
        { x: panel.position.x, y: panel.position.z },
        { x: panel.position.x + panel.size.x, y: panel.position.z },
        { x: panel.position.x + panel.size.x, y: panel.position.z + panel.size.z },
        { x: panel.position.x, y: panel.position.z + panel.size.z }
      ];
      corners.forEach(c => {
        dxf += `10\n${c.x}\n20\n${c.y}\n`;
      });

      panel.holes.forEach(hole => {
        dxf += '0\nINSERT\n2\nDRILL_5x45\n8\nDRILL_5x45\n';
        dxf += `10\n${hole.position.x}\n20\n${hole.position.z}\n`;
        dxf += `999\nDEPTH=${hole.depth}\n`;
      });
    });
    dxf += '0\nENDSEC\n0\nEOF\n';
    return dxf;
  }

  private exportToJSON(solved: Map<string, SolvedPanel>): string {
    return JSON.stringify(Array.from(solved.values()), null, 2);
  }

  private exportToPDF(solved: Map<string, SolvedPanel>, joints: JointTechSpec[]): Buffer {
    const content = `
      ПАНЕЛИ: ${Array.from(solved.values()).map(p => p.id).join(', ')}
      СОЕДИНЕНИЙ: ${joints.length}
    `;
    return Buffer.from(content);
  }

  private exportToGCode(solved: Map<string, SolvedPanel>, joints: JointTechSpec[]): string {
    let gcode = 'G21 ; millimeters\nG90 ; absolute\n';
    solved.forEach(panel => {
      gcode += `; ${panel.id}\n`;
      gcode += 'G0 X0 Y0 Z5\n';
    });
    return gcode;
  }
}

export interface ProductionCabinetModel {
  dsl: CabinetDSL;
  solved: Map<string, SolvedPanel>;
  joints: JointTechSpec[];
  cutting: CuttingPlan;
  validation: { errors: ValidationError[]; warnings: ValidationError[] };
  export: {
    toDXF: () => string;
    toJSON: () => string;
    toPDF: () => Buffer;
    toGCode: () => string;
  };
}
