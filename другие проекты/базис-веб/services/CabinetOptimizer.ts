/**
 * ФАЗА 5: Cabinet Optimizer
 * Параметрическая оптимизация конфигурации шкафа
 * 
 * Использует Genetic Algorithm (GA) для поиска оптимальных параметров конфигурации.
 * Интегрирует DFMValidator, ConstraintSolver и BillOfMaterials для комплексной оценки.
 */

import { OptimizationObjective, OptimizationParams, OptimizedConfig, Assembly, Component, Point3D, CabinetConfig, Section } from '../types/CADTypes';
import { DFMValidator } from './DFMValidator';
import { ConstraintSolver } from './ConstraintSolver';
import { BillOfMaterials } from './BillOfMaterials';

/**
 * Генотип особи в GA (представление конфигурации)
 */
export interface Genome {
  thickness: number;
  width: number;
  height: number;
  depth: number;
  filletRadius: number;
  materialDensity: number;
}

/**
 * Особь в GA (конфигурация + fitness)
 */
export interface Individual {
  genome: Genome;
  fitness: number;
  cost: number;
  weight: number;
  dfmScore: number;
  constraintsSatisfied: boolean;
}

/**
 * Оптимизатор конфигурации шкафа
 */
export class CabinetOptimizer {
  private dfmValidator: DFMValidator;
  private constraintSolver: ConstraintSolver;
  private billOfMaterials: BillOfMaterials;
  private random: () => number = Math.random;

  constructor() {
    this.dfmValidator = new DFMValidator();
    this.constraintSolver = new ConstraintSolver();
    this.billOfMaterials = new BillOfMaterials();
  }

  /**
   * Оптимизировать конфигурацию используя GA
   */
  public optimize(
    baseConfig: CabinetConfig,
    baseSections: Section[],
    assembly: Assembly,
    params: OptimizationParams
  ): OptimizedConfig {
    const startTime = performance.now();
    
    const populationSize = params.populationSize || 20;
    const generations = params.generations || 50;
    const mutationRate = params.mutationRate || 0.1;
    const crossoverRate = params.crossoverRate || 0.8;

    const initialGenome = this.configToGenome(baseConfig);
    const initialFitness = this.evaluateGenome(initialGenome, assembly, baseConfig, baseSections, params);

    let population = this.initializePopulation(initialGenome, populationSize, params);
    let bestIndividual = population.reduce((best, ind) => ind.fitness > best.fitness ? ind : best);

    const fitnessHistory: number[] = [];

    for (let gen = 0; gen < generations; gen++) {
      const nextPopulation: Individual[] = [];

      for (let i = 0; i < populationSize; i += 2) {
        const parent1 = this.selectParent(population);
        const parent2 = this.selectParent(population);

        let child1 = { ...parent1 };
        let child2 = { ...parent2 };

        if (this.random() < crossoverRate) {
          [child1.genome, child2.genome] = this.crossover(parent1.genome, parent2.genome);
        }

        if (this.random() < mutationRate) {
          child1.genome = this.mutate(child1.genome, params);
        }
        if (this.random() < mutationRate) {
          child2.genome = this.mutate(child2.genome, params);
        }

        child1.fitness = this.evaluateGenome(child1.genome, assembly, baseConfig, baseSections, params);
        child2.fitness = this.evaluateGenome(child2.genome, assembly, baseConfig, baseSections, params);

        nextPopulation.push(child1);
        if (nextPopulation.length < populationSize) {
          nextPopulation.push(child2);
        }
      }

      population = nextPopulation.sort((a, b) => b.fitness - a.fitness).slice(0, populationSize);

      const currentBest = population[0];
      if (currentBest.fitness > bestIndividual.fitness) {
        bestIndividual = currentBest;
      }

      fitnessHistory.push(bestIndividual.fitness);
    }

    const optimizedConfig = this.genomeToConfig(bestIndividual.genome, baseConfig, params);
    const originalFitness = initialFitness;
    const improvementPercent = ((bestIndividual.fitness - originalFitness) / Math.abs(originalFitness)) * 100;

    return {
      originalConfig: baseConfig,
      optimizedConfig,
      improvements: {
        costReduction: Math.max(0, (1 - bestIndividual.cost) * 100),
        weightReduction: Math.max(0, (1 - bestIndividual.weight) * 100),
        strengthIncrease: Math.max(0, bestIndividual.dfmScore)
      },
      iterations: generations,
      convergenceTime: performance.now() - startTime,
      score: bestIndividual.fitness
    };
  }

  /**
   * Инициализировать популяцию
   */
  private initializePopulation(
    baseGenome: Genome,
    size: number,
    params: OptimizationParams
  ): Individual[] {
    const population: Individual[] = [];

    for (let i = 0; i < size; i++) {
      const genome: Genome = {
        thickness: baseGenome.thickness + (this.random() - 0.5) * (params.maxThickness || 10),
        width: baseGenome.width + (this.random() - 0.5) * 100,
        height: baseGenome.height + (this.random() - 0.5) * 100,
        depth: baseGenome.depth + (this.random() - 0.5) * 100,
        filletRadius: baseGenome.filletRadius + (this.random() - 0.5) * 5,
        materialDensity: baseGenome.materialDensity + (this.random() - 0.5) * 200
      };

      const config: CabinetConfig = {
        ...{},
        width: genome.width,
        height: genome.height,
        depth: genome.depth,
        thickness: genome.thickness
      } as any;

      const dummyAssembly: Assembly = { id: 'dummy', name: 'dummy', components: [], constraints: [] };
      const fitness = this.evaluateGenome(genome, dummyAssembly, config, [], { objective: OptimizationObjective.BALANCE });

      population.push({
        genome,
        fitness,
        cost: 0,
        weight: 0,
        dfmScore: 0,
        constraintsSatisfied: true
      });
    }

    return population;
  }

  /**
   * Выбрать родителя турнирным отбором
   */
  private selectParent(population: Individual[]): Individual {
    const tournamentSize = Math.ceil(population.length * 0.1);
    let best = population[Math.floor(this.random() * population.length)];

    for (let i = 1; i < tournamentSize; i++) {
      const candidate = population[Math.floor(this.random() * population.length)];
      if (candidate.fitness > best.fitness) {
        best = candidate;
      }
    }

    return best;
  }

  /**
   * Кроссовер (слияние двух геномов)
   */
  private crossover(parent1: Genome, parent2: Genome): [Genome, Genome] {
    const child1: Genome = {
      thickness: this.random() < 0.5 ? parent1.thickness : parent2.thickness,
      width: this.random() < 0.5 ? parent1.width : parent2.width,
      height: this.random() < 0.5 ? parent1.height : parent2.height,
      depth: this.random() < 0.5 ? parent1.depth : parent2.depth,
      filletRadius: this.random() < 0.5 ? parent1.filletRadius : parent2.filletRadius,
      materialDensity: this.random() < 0.5 ? parent1.materialDensity : parent2.materialDensity
    };

    const child2: Genome = {
      thickness: parent1.thickness === child1.thickness ? parent2.thickness : parent1.thickness,
      width: parent1.width === child1.width ? parent2.width : parent1.width,
      height: parent1.height === child1.height ? parent2.height : parent1.height,
      depth: parent1.depth === child1.depth ? parent2.depth : parent1.depth,
      filletRadius: parent1.filletRadius === child1.filletRadius ? parent2.filletRadius : parent1.filletRadius,
      materialDensity: parent1.materialDensity === child1.materialDensity ? parent2.materialDensity : parent1.materialDensity
    };

    return [child1, child2];
  }

  /**
   * Мутация генома
   */
  private mutate(genome: Genome, params: OptimizationParams): Genome {
    const mutationAmount = 0.05;
    const minThickness = params.minThickness || 1;
    const maxThickness = params.maxThickness || 100;

    return {
      thickness: Math.min(
        maxThickness,
        Math.max(minThickness, genome.thickness * (1 + (this.random() - 0.5) * mutationAmount))
      ),
      width: Math.max(100, genome.width * (1 + (this.random() - 0.5) * mutationAmount)),
      height: Math.max(100, genome.height * (1 + (this.random() - 0.5) * mutationAmount)),
      depth: Math.max(100, genome.depth * (1 + (this.random() - 0.5) * mutationAmount)),
      filletRadius: Math.max(0.5, genome.filletRadius * (1 + (this.random() - 0.5) * mutationAmount)),
      materialDensity: Math.max(100, genome.materialDensity * (1 + (this.random() - 0.5) * mutationAmount))
    };
  }

  /**
   * Вычислить fitness геному
   */
  private evaluateGenome(
    genome: Genome,
    assembly: Assembly,
    baseConfig: CabinetConfig,
    baseSections: Section[],
    params: OptimizationParams
  ): number {
    try {
      const config = this.genomeToConfig(genome, baseConfig, params);

      let score = 0;
      let weight = 0;
      let dfmScore = 100;

      weight = genome.thickness * genome.width * genome.height * genome.materialDensity / 1000;
      const cost = weight * 0.5;

      if (assembly.components && assembly.components.length > 0) {
        const dfmReport = this.dfmValidator.validateAssembly(assembly);
        dfmScore = dfmReport.manufacturability;
      }

      switch (params.objective) {
        case OptimizationObjective.COST:
          score = Math.max(0, 100 - cost);
          break;
        case OptimizationObjective.WEIGHT:
          score = Math.max(0, 100 - weight);
          break;
        case OptimizationObjective.STRENGTH:
          score = dfmScore;
          break;
        case OptimizationObjective.BALANCE:
          score = (Math.max(0, 100 - cost) * 0.4 + Math.max(0, 100 - weight) * 0.3 + dfmScore * 0.3);
          break;
      }

      return Math.max(0, score);
    } catch (error) {
      return 0;
    }
  }

  /**
   * Конвертировать конфигурацию в геном
   */
  private configToGenome(config: CabinetConfig): Genome {
    return {
      thickness: config.thickness || 18,
      width: config.width || 600,
      height: config.height || 800,
      depth: config.depth || 500,
      filletRadius: 3,
      materialDensity: 700
    };
  }

  /**
   * Конвертировать геном в конфигурацию
   */
  private genomeToConfig(genome: Genome, baseConfig: CabinetConfig, params?: OptimizationParams): CabinetConfig {
    let thickness = genome.thickness;
    
    if (params) {
      if (params.minThickness) {
        thickness = Math.max(thickness, params.minThickness);
      }
      if (params.maxThickness) {
        thickness = Math.min(thickness, params.maxThickness);
      }
    }

    return {
      ...baseConfig,
      thickness,
      width: genome.width,
      height: genome.height,
      depth: genome.depth
    };
  }
}
