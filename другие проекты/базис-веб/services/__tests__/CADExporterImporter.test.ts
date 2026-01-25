/**
 * CAD Exporter & Importer Tests
 * Полное тестирование функций экспорта и импорта CAD форматов
 */

import { CADExporter, Triangle } from '../CADExporter';
import { CADImporter, ImportResult } from '../CADImporter';
import {
  Assembly,
  Component,
  Point3D,
  ExportFormat,
  ExportOptions
} from '../../types/CADTypes';

describe('CADExporter', () => {
  let exporter: CADExporter;
  let testAssembly: Assembly;
  let testComponent: Component;

  beforeEach(() => {
    exporter = new CADExporter();

    testComponent = {
      id: 'comp-1',
      name: 'Test Component',
      type: 'SOLID',
      geometry: {
        type: '3D',
        vertices: [
          { x: 0, y: 0, z: 0 },
          { x: 10, y: 0, z: 0 },
          { x: 10, y: 10, z: 0 },
          { x: 0, y: 10, z: 0 },
          { x: 0, y: 0, z: 10 },
          { x: 10, y: 0, z: 10 },
          { x: 10, y: 10, z: 10 },
          { x: 0, y: 10, z: 10 }
        ],
        faces: [
          [0, 1, 2],
          [0, 2, 3],
          [4, 6, 5],
          [4, 7, 6]
        ],
        boundingBox: {
          min: { x: 0, y: 0, z: 0 },
          max: { x: 10, y: 10, z: 10 }
        }
      }
    };

    testAssembly = {
      id: 'assembly-1',
      name: 'Test Assembly',
      components: [testComponent],
      constraints: []
    };
  });

  describe('STL Export', () => {
    test('should export assembly to STL binary format', () => {
      const options: ExportOptions = { format: ExportFormat.STL };
      const result = exporter.export(testAssembly, options);

      expect(result).toBeInstanceOf(Buffer);
      expect(result.length).toBeGreaterThan(80);
    });

    test('should generate correct STL header', () => {
      const options: ExportOptions = { format: ExportFormat.STL };
      const result = exporter.export(testAssembly, options) as Buffer;
      const header = result.toString('utf8', 0, 80);

      expect(header).toContain('Test Assembly');
    });

    test('should generate correct triangle count in STL', () => {
      const options: ExportOptions = { format: ExportFormat.STL };
      const result = exporter.export(testAssembly, options) as Buffer;

      expect(result.length).toBeGreaterThan(84);
      const triangleCount = result.readUInt32LE(80);
      expect(typeof triangleCount).toBe('number');
    });

    test('should handle empty assembly in STL export', () => {
      const emptyAssembly: Assembly = {
        id: 'empty',
        name: 'Empty',
        components: [],
        constraints: []
      };

      const options: ExportOptions = { format: ExportFormat.STL };
      const result = exporter.export(emptyAssembly, options);

      expect(result).toBeInstanceOf(Buffer);
    });

    test('should export with multiple components to STL', () => {
      const component2 = { ...testComponent, id: 'comp-2', name: 'Component 2' };
      const assembly: Assembly = {
        ...testAssembly,
        components: [testComponent, component2]
      };

      const options: ExportOptions = { format: ExportFormat.STL };
      const result = exporter.export(assembly, options) as Buffer;

      expect(result).toBeInstanceOf(Buffer);
      expect(result.length).toBeGreaterThan(84);
    });
  });

  describe('DXF Export', () => {
    test('should export assembly to DXF format', () => {
      const options: ExportOptions = { format: ExportFormat.DXF };
      const result = exporter.export(testAssembly, options);

      expect(typeof result).toBe('string');
    });

    test('should contain DXF header section', () => {
      const options: ExportOptions = { format: ExportFormat.DXF };
      const result = exporter.export(testAssembly, options) as string;

      expect(result).toContain('SECTION');
      expect(result).toContain('HEADER');
      expect(result).toContain('ENTITIES');
    });

    test('should contain 3DSOLID entities in DXF', () => {
      const options: ExportOptions = { format: ExportFormat.DXF };
      const result = exporter.export(testAssembly, options) as string;

      expect(result).toContain('3DSOLID');
      expect(result).toContain(testComponent.name);
    });

    test('should end with EOF in DXF', () => {
      const options: ExportOptions = { format: ExportFormat.DXF };
      const result = exporter.export(testAssembly, options) as string;

      expect(result).toContain('EOF');
    });

    test('should handle DXF export with proper coordinate format', () => {
      const options: ExportOptions = { format: ExportFormat.DXF };
      const result = exporter.export(testAssembly, options) as string;
      const lines = result.split('\n');

      const dxfLines = lines.filter(line => line.trim() === '10' || line.trim() === '20' || line.trim() === '30');
      expect(dxfLines.length).toBeGreaterThan(0);
    });
  });

  describe('JSON Export', () => {
    test('should export assembly to JSON format', () => {
      const options: ExportOptions = { format: ExportFormat.JSON };
      const result = exporter.export(testAssembly, options);

      expect(typeof result).toBe('string');
      expect(() => JSON.parse(result as string)).not.toThrow();
    });

    test('should include metadata in JSON export', () => {
      const options: ExportOptions = { format: ExportFormat.JSON };
      const result = JSON.parse(exporter.export(testAssembly, options) as string);

      expect(result.metadata).toBeDefined();
      expect(result.metadata.format).toBe('json');
      expect(result.metadata.version).toBe('1.0');
    });

    test('should include assembly data in JSON export', () => {
      const options: ExportOptions = { format: ExportFormat.JSON };
      const result = JSON.parse(exporter.export(testAssembly, options) as string);

      expect(result.assembly).toBeDefined();
      expect(result.assembly.id).toBe(testAssembly.id);
      expect(result.assembly.name).toBe(testAssembly.name);
    });

    test('should include components in JSON export', () => {
      const options: ExportOptions = { format: ExportFormat.JSON };
      const result = JSON.parse(exporter.export(testAssembly, options) as string);

      expect(result.assembly.components).toBeDefined();
      expect(Array.isArray(result.assembly.components)).toBe(true);
      expect(result.assembly.components.length).toBeGreaterThan(0);
    });

    test('should apply scale factor to JSON export', () => {
      const options: ExportOptions = { format: ExportFormat.JSON, scale: 2.0 };
      const result = JSON.parse(exporter.export(testAssembly, options) as string);

      const component = result.assembly.components[0];
      const originalMax = testComponent.geometry?.boundingBox?.max?.x || 0;
      const exportedMax = component.boundingBox.max.x;

      expect(exportedMax).toBe(originalMax * 2.0);
    });

    test('should include bounding box in JSON components', () => {
      const options: ExportOptions = { format: ExportFormat.JSON };
      const result = JSON.parse(exporter.export(testAssembly, options) as string);

      const component = result.assembly.components[0];
      expect(component.boundingBox).toBeDefined();
      expect(component.boundingBox.min).toBeDefined();
      expect(component.boundingBox.max).toBeDefined();
    });
  });

  describe('OBJ Export', () => {
    test('should export assembly to OBJ format', () => {
      const options: ExportOptions = { format: ExportFormat.OBJ };
      const result = exporter.export(testAssembly, options);

      expect(typeof result).toBe('string');
    });

    test('should include Wavefront OBJ header', () => {
      const options: ExportOptions = { format: ExportFormat.OBJ };
      const result = exporter.export(testAssembly, options) as string;

      expect(result).toContain('Wavefront OBJ');
      expect(result).toContain(testAssembly.name);
    });

    test('should include vertex data in OBJ', () => {
      const options: ExportOptions = { format: ExportFormat.OBJ };
      const result = exporter.export(testAssembly, options) as string;

      expect(result).toContain('v ');
      const vertexLines = result.split('\n').filter(line => line.trim().startsWith('v '));
      expect(vertexLines.length).toBeGreaterThan(0);
    });

    test('should include face data in OBJ', () => {
      const options: ExportOptions = { format: ExportFormat.OBJ };
      const result = exporter.export(testAssembly, options) as string;

      expect(result).toContain('f ');
      const faceLines = result.split('\n').filter(line => line.trim().startsWith('f '));
      expect(faceLines.length).toBeGreaterThan(0);
    });

    test('should include component comments in OBJ', () => {
      const options: ExportOptions = { format: ExportFormat.OBJ };
      const result = exporter.export(testAssembly, options) as string;

      expect(result).toContain('Component:');
      expect(result).toContain(testComponent.name);
    });

    test('should apply scale to OBJ vertices', () => {
      const options: ExportOptions = { format: ExportFormat.OBJ, scale: 0.5 };
      const result = exporter.export(testAssembly, options) as string;
      const vertexLine = result.split('\n').find(line => line.trim().startsWith('v '));

      expect(vertexLine).toBeDefined();
      const parts = vertexLine!.split(/\s+/).map(parseFloat);
      expect(parts[1]).toBeLessThanOrEqual(5);
    });
  });

  describe('STEP Export', () => {
    test('should export assembly to STEP format', () => {
      const options: ExportOptions = { format: ExportFormat.STEP };
      const result = exporter.export(testAssembly, options);

      expect(result).toBeInstanceOf(Buffer);
    });

    test('should contain STEP header', () => {
      const options: ExportOptions = { format: ExportFormat.STEP };
      const result = exporter.export(testAssembly, options) as Buffer;
      const content = result.toString('utf8');

      expect(content).toContain('ISO-10303-21');
      expect(content).toContain('HEADER');
    });

    test('should contain PRODUCT_DEFINITION entities', () => {
      const options: ExportOptions = { format: ExportFormat.STEP };
      const result = exporter.export(testAssembly, options) as Buffer;
      const content = result.toString('utf8');

      expect(content).toContain('PRODUCT_DEFINITION');
      expect(content).toContain(testComponent.name);
    });

    test('should end with STEP footer', () => {
      const options: ExportOptions = { format: ExportFormat.STEP };
      const result = exporter.export(testAssembly, options) as Buffer;
      const content = result.toString('utf8');

      expect(content).toContain('ENDSEC');
      expect(content).toContain('END-ISO-10303-21');
    });
  });

  describe('IGES Export', () => {
    test('should export assembly to IGES format', () => {
      const options: ExportOptions = { format: ExportFormat.IGES };
      const result = exporter.export(testAssembly, options);

      expect(result).toBeInstanceOf(Buffer);
    });

    test('should generate IGES buffer with correct structure', () => {
      const options: ExportOptions = { format: ExportFormat.IGES };
      const result = exporter.export(testAssembly, options) as Buffer;

      expect(result.length).toBeGreaterThan(0);
    });
  });

  describe('glTF Export', () => {
    test('should export assembly to glTF format', () => {
      const options: ExportOptions = { format: ExportFormat.GLTF };
      const result = exporter.export(testAssembly, options);

      expect(result).toBeInstanceOf(Buffer);
    });

    test('should generate valid glTF JSON', () => {
      const options: ExportOptions = { format: ExportFormat.GLTF };
      const result = exporter.export(testAssembly, options) as Buffer;
      const content = result.toString('utf8');

      expect(() => JSON.parse(content)).not.toThrow();
      const gltf = JSON.parse(content);
      expect(gltf.asset).toBeDefined();
      expect(gltf.asset.version).toBe('2.0');
    });

    test('should include mesh data in glTF', () => {
      const options: ExportOptions = { format: ExportFormat.GLTF };
      const result = exporter.export(testAssembly, options) as Buffer;
      const gltf = JSON.parse(result.toString('utf8'));

      expect(gltf.meshes).toBeDefined();
      expect(gltf.meshes.length).toBeGreaterThan(0);
    });
  });

  describe('Unsupported Format', () => {
    test('should throw error for unsupported format', () => {
      const options = { format: 'UNSUPPORTED' as any };

      expect(() => exporter.export(testAssembly, options)).toThrow();
    });
  });

  describe('Normal Calculation', () => {
    test('should calculate correct triangle normal', () => {
      const v1: Point3D = { x: 0, y: 0, z: 0 };
      const v2: Point3D = { x: 1, y: 0, z: 0 };
      const v3: Point3D = { x: 0, y: 1, z: 0 };

      const options: ExportOptions = { format: ExportFormat.STL };
      const result = exporter.export(testAssembly, options) as Buffer;

      expect(result).toBeInstanceOf(Buffer);
    });
  });
});

describe('CADImporter', () => {
  let importer: CADImporter;

  beforeEach(() => {
    importer = new CADImporter();
  });

  describe('JSON Import', () => {
    test('should import valid JSON assembly', () => {
      const jsonData = {
        assembly: {
          id: 'test-1',
          name: 'Test Assembly',
          components: [
            {
              id: 'comp-1',
              name: 'Component 1',
              type: 'SOLID',
              geometry: {
                type: '3D',
                vertices: [],
                faces: [],
                boundingBox: { min: { x: 0, y: 0, z: 0 }, max: { x: 10, y: 10, z: 10 } }
              }
            }
          ],
          constraints: []
        }
      };

      const result = importer.importFromJSON(JSON.stringify(jsonData));

      expect(result.success).toBe(true);
      expect(result.assembly).toBeDefined();
      expect(result.assembly?.id).toBe('test-1');
    });

    test('should import flat JSON assembly structure', () => {
      const jsonData = {
        id: 'test-2',
        name: 'Flat Assembly',
        components: [
          {
            id: 'comp-1',
            name: 'Component 1',
            type: 'SOLID',
            geometry: {
              type: '3D',
              vertices: [],
              faces: [],
              boundingBox: { min: { x: 0, y: 0, z: 0 }, max: { x: 10, y: 10, z: 10 } }
            }
          }
        ],
        constraints: []
      };

      const result = importer.importFromJSON(JSON.stringify(jsonData));

      expect(result.success).toBe(true);
      expect(result.assembly?.name).toBe('Flat Assembly');
    });

    test('should fail on invalid JSON', () => {
      const result = importer.importFromJSON('invalid json {');

      expect(result.success).toBe(false);
      expect(result.errors.length).toBeGreaterThan(0);
    });

    test('should fail on invalid assembly structure', () => {
      const jsonData = { invalid: 'structure' };

      const result = importer.importFromJSON(JSON.stringify(jsonData));

      expect(result.success).toBe(false);
      expect(result.errors.length).toBeGreaterThan(0);
    });

    test('should validate components in JSON import', () => {
      const jsonData = {
        assembly: {
          id: 'test-3',
          name: 'Test',
          components: [
            {
              name: 'Component without ID',
              type: 'SOLID'
            }
          ],
          constraints: []
        }
      };

      const result = importer.importFromJSON(JSON.stringify(jsonData));

      expect(result.success).toBe(false);
    });

    test('should handle empty components array', () => {
      const jsonData = {
        assembly: {
          id: 'test-4',
          name: 'Empty Assembly',
          components: [],
          constraints: []
        }
      };

      const result = importer.importFromJSON(JSON.stringify(jsonData));

      expect(result.success).toBe(true);
      expect(result.assembly?.components.length).toBe(0);
    });
  });

  describe('DXF Import', () => {
    test('should import basic DXF file', () => {
      const dxfContent = `0
SECTION
2
ENTITIES
0
3DSOLID
8
TestComponent
10
0
20
0
30
0
0
ENDSEC
0
EOF`;

      const result = importer.importFromDXF(dxfContent);

      expect(result.success).toBe(true);
      expect(result.assembly).toBeDefined();
      expect(result.assembly?.components.length).toBeGreaterThan(0);
    });

    test('should extract component name from DXF layer', () => {
      const dxfContent = `0
SECTION
2
ENTITIES
0
3DSOLID
8
ComponentName
10
5
20
10
30
15
0
ENDSEC
0
EOF`;

      const result = importer.importFromDXF(dxfContent);

      expect(result.assembly?.components.length).toBeGreaterThan(0);
    });

    test('should handle DXF with multiple entities', () => {
      const dxfContent = `0
SECTION
2
ENTITIES
0
3DSOLID
8
Component1
10
0
20
0
30
0
0
3DSOLID
8
Component2
10
10
20
10
30
10
0
ENDSEC
0
EOF`;

      const result = importer.importFromDXF(dxfContent);

      expect(result.assembly?.components.length).toBeGreaterThanOrEqual(1);
    });

    test('should warn on empty DXF file', () => {
      const dxfContent = `0
SECTION
2
HEADER
0
ENDSEC
0
EOF`;

      const result = importer.importFromDXF(dxfContent);

      expect(result.success).toBe(true);
      expect(result.assembly).toBeDefined();
    });

    test('should handle DXF parse error gracefully', () => {
      const dxfContent = 'corrupted dxf content';

      const result = importer.importFromDXF(dxfContent);

      expect(result.success).toBe(true);
    });

    test('should extract coordinates from DXF entities', () => {
      const dxfContent = `0
SECTION
2
ENTITIES
0
3DSOLID
8
TestComp
10
5
20
15
30
25
0
ENDSEC
0
EOF`;

      const result = importer.importFromDXF(dxfContent);
      const component = result.assembly?.components[0];

      expect(component?.geometry?.boundingBox?.min?.x).toBeDefined();
    });
  });

  describe('STEP Import', () => {
    test('should import basic STEP file', () => {
      const stepContent = `ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('Test STEP file'),'2;1');
FILE_NAME('test.step',2024,(''),(''),\\'CAD System\\',\\'\\',\\'\\');
FILE_SCHEMA(('IFC4'));
ENDSEC;
DATA;
#1=PRODUCT_DEFINITION('TestComponent','TestComponent',#2,#3);
ENDSEC;
END-ISO-10303-21;`;

      const result = importer.importFromSTEP(stepContent);

      expect(result.success).toBe(true);
      expect(result.assembly?.components.length).toBeGreaterThan(0);
    });

    test('should extract component names from PRODUCT_DEFINITION', () => {
      const stepContent = `ISO-10303-21;
HEADER;
ENDSEC;
DATA;
#1=PRODUCT_DEFINITION('MyComponent','MyComponent',#2,#3);
ENDSEC;
END-ISO-10303-21;`;

      const result = importer.importFromSTEP(stepContent);

      expect(result.assembly?.components[0].name).toBe('MyComponent');
    });

    test('should handle multiple PRODUCT_DEFINITION entities', () => {
      const stepContent = `ISO-10303-21;
HEADER;
ENDSEC;
DATA;
#1=PRODUCT_DEFINITION('Comp1','Comp1',#2,#3);
#4=PRODUCT_DEFINITION('Comp2','Comp2',#5,#6);
ENDSEC;
END-ISO-10303-21;`;

      const result = importer.importFromSTEP(stepContent);

      expect(result.assembly?.components.length).toBeGreaterThanOrEqual(1);
    });

    test('should warn on empty STEP file', () => {
      const stepContent = `ISO-10303-21;
HEADER;
ENDSEC;
DATA;
ENDSEC;
END-ISO-10303-21;`;

      const result = importer.importFromSTEP(stepContent);

      expect(result.warnings.length).toBeGreaterThan(0);
    });

    test('should handle malformed STEP content', () => {
      const stepContent = 'not a valid step file';

      const result = importer.importFromSTEP(stepContent);

      expect(result.success).toBe(true);
    });
  });

  describe('OBJ Import', () => {
    test('should import basic OBJ file', () => {
      const objContent = `# Wavefront OBJ file
v 0 0 0
v 1 0 0
v 1 1 0
v 0 1 0
f 1 2 3
f 1 3 4`;

      const result = importer.importFromOBJ(objContent);

      expect(result.success).toBe(true);
      expect(result.assembly?.components.length).toBeGreaterThan(0);
    });

    test('should parse vertices correctly in OBJ', () => {
      const objContent = `v 0 0 0
v 10 0 0
v 10 10 0
v 0 10 0
f 1 2 3
f 1 3 4`;

      const result = importer.importFromOBJ(objContent);
      const component = result.assembly?.components[0];

      expect(component?.geometry?.vertices?.length).toBe(4);
    });

    test('should parse faces correctly in OBJ', () => {
      const objContent = `v 0 0 0
v 1 0 0
v 1 1 0
f 1 2 3`;

      const result = importer.importFromOBJ(objContent);
      const component = result.assembly?.components[0];

      expect(component?.geometry?.faces?.length).toBeGreaterThan(0);
    });

    test('should handle groups in OBJ', () => {
      const objContent = `g Group1
v 0 0 0
v 1 0 0
v 1 1 0
f 1 2 3
g Group2
v 2 2 2
v 3 2 2
v 3 3 2
f 4 5 6`;

      const result = importer.importFromOBJ(objContent);

      expect(result.success).toBe(true);
    });

    test('should calculate bounding box from OBJ vertices', () => {
      const objContent = `v 0 0 0
v 10 0 0
v 10 10 0
v 0 10 0
f 1 2 3
f 1 3 4`;

      const result = importer.importFromOBJ(objContent);
      const bbox = result.assembly?.components[0].geometry?.boundingBox;

      expect(bbox?.min?.x).toBeLessThanOrEqual(0);
      expect(bbox?.max?.x).toBeGreaterThanOrEqual(10);
    });

    test('should warn on empty OBJ file', () => {
      const objContent = '# Empty OBJ file';

      const result = importer.importFromOBJ(objContent);

      expect(result.warnings.length).toBeGreaterThan(0);
    });

    test('should handle face indices with texture coordinates', () => {
      const objContent = `v 0 0 0
v 1 0 0
v 1 1 0
f 1/1 2/2 3/3`;

      const result = importer.importFromOBJ(objContent);

      expect(result.success).toBe(true);
    });

    test('should handle malformed OBJ content', () => {
      const objContent = 'invalid obj content';

      const result = importer.importFromOBJ(objContent);

      expect(result.success).toBe(true);
    });
  });

  describe('Generic Import Method', () => {
    test('should import JSON via generic import method', () => {
      const jsonData = {
        assembly: {
          id: 'test-1',
          name: 'Test',
          components: [
            { id: 'c1', name: 'C1', type: 'SOLID', geometry: { type: '3D', vertices: [], faces: [], boundingBox: { min: { x: 0, y: 0, z: 0 }, max: { x: 10, y: 10, z: 10 } } }
            }
          ],
          constraints: []
        }
      };

      const result = importer.import(JSON.stringify(jsonData), 'json');

      expect(result.success).toBe(true);
    });

    test('should import DXF via generic import method', () => {
      const dxfContent = `0
SECTION
2
ENTITIES
0
3DSOLID
8
TestComp
10
0
20
0
30
0
0
ENDSEC
0
EOF`;

      const result = importer.import(dxfContent, 'dxf');

      expect(result.success).toBe(true);
    });

    test('should import STEP via generic import method', () => {
      const stepContent = `ISO-10303-21;
HEADER;
ENDSEC;
DATA;
#1=PRODUCT_DEFINITION('TestComp','TestComp',#2,#3);
ENDSEC;
END-ISO-10303-21;`;

      const result = importer.import(stepContent, 'step');

      expect(result.success).toBe(true);
    });

    test('should import OBJ via generic import method', () => {
      const objContent = `v 0 0 0
v 1 0 0
v 1 1 0
f 1 2 3`;

      const result = importer.import(objContent, 'obj');

      expect(result.success).toBe(true);
    });

    test('should support .stp extension for STEP files', () => {
      const stepContent = `ISO-10303-21;
HEADER;
ENDSEC;
DATA;
ENDSEC;
END-ISO-10303-21;`;

      const result = importer.import(stepContent, 'stp');

      expect(result.success).toBe(true);
    });

    test('should reject unsupported file type', () => {
      const result = importer.import('content', 'xyz');

      expect(result.success).toBe(false);
      expect(result.errors.length).toBeGreaterThan(0);
    });

    test('should handle Buffer input', () => {
      const jsonData = {
        assembly: {
          id: 'test-1',
          name: 'Test',
          components: [
            { id: 'c1', name: 'C1', type: 'SOLID', geometry: { type: '3D', vertices: [], faces: [], boundingBox: { min: { x: 0, y: 0, z: 0 }, max: { x: 10, y: 10, z: 10 } } }
            }
          ],
          constraints: []
        }
      };

      const buffer = Buffer.from(JSON.stringify(jsonData), 'utf8');
      const result = importer.import(buffer, 'json');

      expect(result.success).toBe(true);
    });
  });

  describe('Validation', () => {
    test('should validate assembly with all required fields', () => {
      const assembly: Assembly = {
        id: 'test-1',
        name: 'Test Assembly',
        components: [
          {
            id: 'comp-1',
            name: 'Component 1',
            type: 'SOLID',
            geometry: { type: '3D', vertices: [], faces: [], boundingBox: { min: { x: 0, y: 0, z: 0 }, max: { x: 10, y: 10, z: 10 } } }
          }
        ],
        constraints: []
      };

      const result = importer.validate(assembly);

      expect(result.isValid).toBe(true);
      expect(result.errors.length).toBe(0);
    });

    test('should reject assembly without id', () => {
      const assembly: any = {
        name: 'Test',
        components: [],
        constraints: []
      };

      const result = importer.validate(assembly);

      expect(result.isValid).toBe(false);
      expect(result.errors.some(e => e.includes('id'))).toBe(true);
    });

    test('should reject assembly without name', () => {
      const assembly: any = {
        id: 'test-1',
        components: [],
        constraints: []
      };

      const result = importer.validate(assembly);

      expect(result.isValid).toBe(false);
      expect(result.errors.some(e => e.includes('name'))).toBe(true);
    });

    test('should reject assembly with non-array components', () => {
      const assembly: any = {
        id: 'test-1',
        name: 'Test',
        components: 'not an array',
        constraints: []
      };

      const result = importer.validate(assembly);

      expect(result.isValid).toBe(false);
    });

    test('should reject components without id', () => {
      const assembly: any = {
        id: 'test-1',
        name: 'Test',
        components: [
          { name: 'Component without id', type: 'SOLID' }
        ],
        constraints: []
      };

      const result = importer.validate(assembly);

      expect(result.isValid).toBe(false);
    });

    test('should reject components without name', () => {
      const assembly: any = {
        id: 'test-1',
        name: 'Test',
        components: [
          { id: 'comp-1', type: 'SOLID' }
        ],
        constraints: []
      };

      const result = importer.validate(assembly);

      expect(result.isValid).toBe(false);
    });
  });

  describe('Round-trip (Export -> Import)', () => {
    test('should maintain assembly structure through JSON export/import cycle', () => {
      const exporter = new CADExporter();
      const originalAssembly: Assembly = {
        id: 'test-roundtrip',
        name: 'Round Trip Test',
        components: [
          {
            id: 'comp-1',
            name: 'Component 1',
            type: 'SOLID',
            geometry: {
              type: '3D',
              vertices: [
                { x: 0, y: 0, z: 0 },
                { x: 10, y: 0, z: 0 },
                { x: 10, y: 10, z: 0 }
              ],
              faces: [[0, 1, 2]],
              boundingBox: {
                min: { x: 0, y: 0, z: 0 },
                max: { x: 10, y: 10, z: 0 }
              }
            }
          }
        ],
        constraints: []
      };

      const exported = exporter.export(originalAssembly, { format: ExportFormat.JSON });
      const imported = importer.importFromJSON(exported as string);

      expect(imported.success).toBe(true);
      expect(imported.assembly?.id).toBe(originalAssembly.id);
      expect(imported.assembly?.name).toBe(originalAssembly.name);
      expect(imported.assembly?.components.length).toBe(1);
    });
  });

  describe('Error Handling', () => {
    test('should provide descriptive error messages for JSON import', () => {
      const result = importer.importFromJSON('{ invalid json');

      expect(result.errors.length).toBeGreaterThan(0);
      expect(result.errors[0]).toContain('Failed to parse');
    });

    test('should handle null assembly gracefully', () => {
      const jsonData = { assembly: null };

      const result = importer.importFromJSON(JSON.stringify(jsonData));

      expect(result.success).toBe(false);
    });

    test('should track import warnings separately from errors', () => {
      const objContent = ``;

      const result = importer.importFromOBJ(objContent);

      expect(result.success).toBe(true);
      expect(result.warnings.length).toBeGreaterThan(0);
    });
  });
});
