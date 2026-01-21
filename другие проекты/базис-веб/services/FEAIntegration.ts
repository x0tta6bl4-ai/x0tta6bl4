/**
 * ФАЗА 7: FEA Integration
 * Конечно-элементный анализ - расчёт прочности и собственных частот
 */

import { FEAMesh, FEANode, FEAElement, LoadCase, FEAResult, ModalAnalysisResult, VibrationMode, Material, Point3D, Load, BoundaryCondition } from '../types/CADTypes';

export interface FEAComponent {
  geometry?: {
    boundingBox?: {
      min: Point3D;
      max: Point3D;
    };
    vertices?: Point3D[];
    faces?: number[][];
  };
}

export class FEAIntegration {
  private youngModulus: { [key: string]: number } = {
    'aluminum': 69000,
    'steel': 210000,
    'plastic': 3000,
    'copper': 130000,
    'default': 200000
  };

  private poissonsRatio: { [key: string]: number } = {
    'aluminum': 0.33,
    'steel': 0.30,
    'plastic': 0.35,
    'copper': 0.34,
    'default': 0.30
  };

  private density: { [key: string]: number } = {
    'aluminum': 2700,
    'steel': 7850,
    'plastic': 1200,
    'copper': 8960,
    'default': 5000
  };

  public generateMesh(component: FEAComponent, elementSize: number = 10): FEAMesh {
    const nodes: FEANode[] = [];
    const elements: FEAElement[] = [];

    if (!component.geometry?.boundingBox) {
      return { nodes: [], elements: [], elementSize, totalElements: 0, totalNodes: 0 };
    }

    const bbox = component.geometry.boundingBox;
    const min = bbox.min || { x: 0, y: 0, z: 0 };
    const max = bbox.max || { x: 100, y: 100, z: 100 };

    const numX = Math.ceil((max.x - min.x) / elementSize) || 2;
    const numY = Math.ceil((max.y - min.y) / elementSize) || 2;
    const numZ = Math.ceil((max.z - min.z) / elementSize) || 2;

    const dX = (max.x - min.x) / numX;
    const dY = (max.y - min.y) / numY;
    const dZ = (max.z - min.z) / numZ;

    let nodeId = 0;
    const nodeGrid: number[][][] = [];

    for (let i = 0; i <= numX; i++) {
      nodeGrid[i] = [];
      for (let j = 0; j <= numY; j++) {
        nodeGrid[i][j] = [];
        for (let k = 0; k <= numZ; k++) {
          nodes.push({
            id: nodeId,
            position: {
              x: min.x + i * dX,
              y: min.y + j * dY,
              z: min.z + k * dZ
            }
          });
          nodeGrid[i][j][k] = nodeId++;
        }
      }
    }

    for (let i = 0; i < numX; i++) {
      for (let j = 0; j < numY; j++) {
        for (let k = 0; k < numZ; k++) {
          const n0 = nodeGrid[i][j][k];
          const n1 = nodeGrid[i + 1][j][k];
          const n2 = nodeGrid[i][j + 1][k];
          const n3 = nodeGrid[i][j][k + 1];
          const n4 = nodeGrid[i + 1][j + 1][k];
          const n5 = nodeGrid[i + 1][j][k + 1];
          const n6 = nodeGrid[i][j + 1][k + 1];
          const n7 = nodeGrid[i + 1][j + 1][k + 1];

          elements.push({ id: elements.length, nodeIndices: [n0, n1, n2, n3], material: { id: 'default', name: 'Default' } });
          elements.push({ id: elements.length, nodeIndices: [n1, n4, n2, n7], material: { id: 'default', name: 'Default' } });
          elements.push({ id: elements.length, nodeIndices: [n1, n5, n3, n7], material: { id: 'default', name: 'Default' } });
          elements.push({ id: elements.length, nodeIndices: [n3, n6, n2, n7], material: { id: 'default', name: 'Default' } });
          elements.push({ id: elements.length, nodeIndices: [n1, n3, n2, n7], material: { id: 'default', name: 'Default' } });
        }
      }
    }

    return {
      nodes,
      elements,
      elementSize,
      totalElements: elements.length,
      totalNodes: nodes.length
    };
  }

  public runLinearStaticAnalysis(
    mesh: FEAMesh,
    material: Material,
    loadCase: LoadCase
  ): FEAResult {
    const startTime = Date.now();
    const numNodes = mesh.nodes.length;
    const dof = numNodes * 3;

    const K = this.assembleGlobalStiffnessMatrix(mesh, material);
    const F = this.assembleLoadVector(mesh, loadCase, numNodes);

    const activeK: number[][] = [];
    const activeF: number[] = [];
    const dofMapping: number[] = [];

    let activeDOF = 0;
    for (let i = 0; i < dof; i++) {
      let isActive = true;
      for (const bc of loadCase.boundaryConditions) {
        const nodeId = bc.nodeId;
        const localDOF = i % 3;
        if (nodeId * 3 + localDOF === i && bc.fixed[localDOF]) {
          isActive = false;
          break;
        }
      }
      if (isActive) {
        dofMapping[i] = activeDOF++;
      } else {
        dofMapping[i] = -1;
      }
    }

    for (let i = 0; i < K.length; i++) {
      if (dofMapping[i] >= 0) {
        const row: number[] = [];
        for (let j = 0; j < K[i].length; j++) {
          if (dofMapping[j] >= 0) {
            row.push(K[i][j]);
          }
        }
        activeK.push(row);
        activeF.push(F[i]);
      }
    }

    const u = this.solveLinearSystem(activeK, activeF);
    const fullDisplacements = new Array(dof).fill(0);
    let uIdx = 0;
    for (let i = 0; i < dof; i++) {
      if (dofMapping[i] >= 0) {
        fullDisplacements[i] = u[uIdx++];
      }
    }

    const displacements: Point3D[] = [];
    let maxDisplacement = 0;
    for (let i = 0; i < numNodes; i++) {
      const dx = fullDisplacements[i * 3];
      const dy = fullDisplacements[i * 3 + 1];
      const dz = fullDisplacements[i * 3 + 2];
      displacements.push({ x: dx, y: dy, z: dz });
      const disp = Math.sqrt(dx * dx + dy * dy + dz * dz);
      if (disp > maxDisplacement) maxDisplacement = disp;
    }

    const stress: number[] = [];
    let maxStress = 0;
    for (const element of mesh.elements) {
      const elementStress = this.computeElementStress(element, mesh.nodes, displacements, material);
      stress.push(elementStress);
      if (elementStress > maxStress) maxStress = elementStress;
    }

    const E = this.youngModulus[material.id] || this.youngModulus['default'];
    const nu = this.poissonsRatio[material.id] || this.poissonsRatio['default'];
    const yieldStress = 250;
    const safetyFactor = maxStress > 0 ? yieldStress / maxStress : 1.0;

    const strain: number[] = stress.map(s => s / E);
    const maxStrain = Math.max(...strain);

    const strainEnergy = fullDisplacements.reduce((sum, u, i) => sum + 0.5 * F[i] * u, 0);

    return {
      displacements,
      stress,
      strain,
      maxDisplacement,
      maxStress,
      maxStrain,
      safetyFactor,
      strainEnergy,
      loadCaseName: loadCase.name,
      solverTime: Date.now() - startTime,
      timestamp: new Date()
    };
  }

  public runModalAnalysis(
    mesh: FEAMesh,
    material: Material,
    numModes: number = 5
  ): ModalAnalysisResult {
    const startTime = Date.now();
    const K = this.assembleGlobalStiffnessMatrix(mesh, material);
    const M = this.assembleMassMatrix(mesh, material);

    const eigenpairs = this.computeEigenvalues(K, M, numModes);

    const modes: VibrationMode[] = [];
    for (let i = 0; i < eigenpairs.length; i++) {
      const omega = Math.sqrt(eigenpairs[i].value);
      const frequency = omega / (2 * Math.PI);
      modes.push({
        mode: i + 1,
        frequency: frequency >= 0 ? frequency : 0,
        period: frequency > 0 ? 1 / frequency : 0,
        dampingRatio: 0.05,
        displacements: eigenpairs[i].vector.map((_, idx) => ({
          x: eigenpairs[i].vector[idx * 3] || 0,
          y: eigenpairs[i].vector[idx * 3 + 1] || 0,
          z: eigenpairs[i].vector[idx * 3 + 2] || 0
        }))
      });
    }

    return {
      modes,
      solverTime: Date.now() - startTime,
      timestamp: new Date()
    };
  }

  private assembleGlobalStiffnessMatrix(mesh: FEAMesh, material: Material): number[][] {
    const dof = mesh.nodes.length * 3;
    const K: number[][] = Array.from({ length: dof }, () => Array(dof).fill(0));

    for (const element of mesh.elements) {
      const Ke = this.computeElementStiffness(element, mesh.nodes, material);
      const indices = element.nodeIndices.flatMap(nodeIdx => [nodeIdx * 3, nodeIdx * 3 + 1, nodeIdx * 3 + 2]);

      for (let i = 0; i < indices.length; i++) {
        for (let j = 0; j < indices.length; j++) {
          K[indices[i]][indices[j]] += Ke[i][j];
        }
      }
    }

    return K;
  }

  private assembleMassMatrix(mesh: FEAMesh, material: Material): number[][] {
    const dof = mesh.nodes.length * 3;
    const M: number[][] = Array.from({ length: dof }, () => Array(dof).fill(0));

    const rho = this.density[material.id] || this.density['default'];
    const volume = this.estimateComponentVolume(mesh);
    const totalMass = rho * volume / 1e9;
    const massPerNode = totalMass / mesh.nodes.length;

    for (let i = 0; i < mesh.nodes.length; i++) {
      M[i * 3][i * 3] = massPerNode;
      M[i * 3 + 1][i * 3 + 1] = massPerNode;
      M[i * 3 + 2][i * 3 + 2] = massPerNode;
    }

    return M;
  }

  private computeElementStiffness(element: FEAElement, nodes: FEANode[], material: Material): number[][] {
    const E = this.youngModulus[material.id] || this.youngModulus['default'];
    const nu = this.poissonsRatio[material.id] || this.poissonsRatio['default'];

    const nodePositions = element.nodeIndices.map(idx => nodes[idx].position);
    const volume = this.tetrahedronVolume(nodePositions);

    const size = element.nodeIndices.length * 3;
    const Ke: number[][] = Array.from({ length: size }, () => Array(size).fill(0));

    const stiffness = (E * volume) / (12 * (1 - 2 * nu));
    for (let i = 0; i < size; i++) {
      Ke[i][i] = stiffness;
      for (let j = i + 1; j < size; j++) {
        Ke[i][j] = Ke[j][i] = stiffness * 0.25;
      }
    }

    return Ke;
  }

  private computeElementStress(element: FEAElement, nodes: FEANode[], displacements: Point3D[], material: Material): number {
    const E = this.youngModulus[material.id] || this.youngModulus['default'];
    const nu = this.poissonsRatio[material.id] || this.poissonsRatio['default'];

    let strainEnergy = 0;
    for (const nodeIdx of element.nodeIndices) {
      const disp = displacements[nodeIdx];
      strainEnergy += disp.x * disp.x + disp.y * disp.y + disp.z * disp.z;
    }

    const stress = Math.sqrt(strainEnergy) * E / (2 * (1 - nu));
    return stress;
  }

  private tetrahedronVolume(nodes: Point3D[]): number {
    if (nodes.length < 4) return 1;

    const v1 = { x: nodes[1].x - nodes[0].x, y: nodes[1].y - nodes[0].y, z: nodes[1].z - nodes[0].z };
    const v2 = { x: nodes[2].x - nodes[0].x, y: nodes[2].y - nodes[0].y, z: nodes[2].z - nodes[0].z };
    const v3 = { x: nodes[3].x - nodes[0].x, y: nodes[3].y - nodes[0].y, z: nodes[3].z - nodes[0].z };

    const cross = {
      x: v1.y * v2.z - v1.z * v2.y,
      y: v1.z * v2.x - v1.x * v2.z,
      z: v1.x * v2.y - v1.y * v2.x
    };

    const volume = Math.abs((cross.x * v3.x + cross.y * v3.y + cross.z * v3.z) / 6);
    return volume || 1;
  }

  private estimateComponentVolume(mesh: FEAMesh): number {
    let volume = 0;
    for (const element of mesh.elements) {
      const nodePositions = element.nodeIndices.map(idx => mesh.nodes[idx].position);
      volume += this.tetrahedronVolume(nodePositions);
    }
    return volume;
  }

  private assembleLoadVector(mesh: FEAMesh, loadCase: LoadCase, numNodes: number): number[] {
    const F = new Array(numNodes * 3).fill(0);

    for (const load of loadCase.loads) {
      const nodeId = load.nodeId;
      if (nodeId < numNodes) {
        F[nodeId * 3] += load.force.x;
        F[nodeId * 3 + 1] += load.force.y;
        F[nodeId * 3 + 2] += load.force.z;
      }
    }

    return F;
  }

  private solveLinearSystem(K: number[][], F: number[]): number[] {
    const n = K.length;
    const A = K.map(row => [...row]);
    const b = [...F];

    for (let i = 0; i < n; i++) {
      let maxRow = i;
      for (let j = i + 1; j < n; j++) {
        if (Math.abs(A[j][i]) > Math.abs(A[maxRow][i])) {
          maxRow = j;
        }
      }

      [A[i], A[maxRow]] = [A[maxRow], A[i]];
      [b[i], b[maxRow]] = [b[maxRow], b[i]];

      if (Math.abs(A[i][i]) < 1e-10) continue;

      for (let j = i + 1; j < n; j++) {
        const factor = A[j][i] / A[i][i];
        for (let k = i; k < n; k++) {
          A[j][k] -= factor * A[i][k];
        }
        b[j] -= factor * b[i];
      }
    }

    const x = new Array(n).fill(0);
    for (let i = n - 1; i >= 0; i--) {
      x[i] = b[i];
      for (let j = i + 1; j < n; j++) {
        x[i] -= A[i][j] * x[j];
      }
      x[i] /= A[i][i] || 1;
    }

    return x;
  }

  private computeEigenvalues(K: number[][], M: number[][], numModes: number): Array<{ value: number; vector: number[] }> {
    const n = K.length;
    const eigenvalues: Array<{ value: number; vector: number[] }> = [];

    for (let mode = 0; mode < Math.min(numModes, n); mode++) {
      let eigenvalue = 1.0;
      let eigenvector = new Array(n).fill(1 / Math.sqrt(n));

      for (let iter = 0; iter < 20; iter++) {
        const Kv = this.matrixVectorProduct(K, eigenvector);
        const Mv = this.matrixVectorProduct(M, eigenvector);

        eigenvalue = this.vectorDot(Kv, eigenvector) / this.vectorDot(Mv, eigenvector);

        const nextVector = new Array(n).fill(0);
        for (let i = 0; i < n; i++) {
          nextVector[i] = (Kv[i] - eigenvalue * Mv[i]) / (eigenvalue + 1);
        }

        const norm = Math.sqrt(this.vectorDot(nextVector, nextVector));
        if (norm > 1e-10) {
          eigenvector = nextVector.map(v => v / norm);
        }
      }

      eigenvalues.push({ value: eigenvalue, vector: eigenvector });
    }

    return eigenvalues;
  }

  private matrixVectorProduct(A: number[][], v: number[]): number[] {
    const result = new Array(A.length).fill(0);
    for (let i = 0; i < A.length; i++) {
      for (let j = 0; j < v.length; j++) {
        result[i] += A[i][j] * v[j];
      }
    }
    return result;
  }

  private vectorDot(a: number[], b: number[]): number {
    return a.reduce((sum, val, i) => sum + val * b[i], 0);
  }
}
