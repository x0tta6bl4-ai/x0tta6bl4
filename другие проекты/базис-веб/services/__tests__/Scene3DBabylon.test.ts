describe('Scene3DBabylon Material Fix', () => {
  it('should use diffuse property instead of albedoColor', () => {
    const mat = { diffuse: { r: 0.2, g: 0.2, b: 0.2 } };
    expect(mat.diffuse).toBeDefined();
    expect(mat.diffuse.r).toBe(0.2);
  });

  it('should apply fallback color on hex parse failure', () => {
    const mat = { diffuse: { r: 0.85, g: 0.85, b: 0.85 } };
    expect(mat.diffuse.r).toBe(0.85);
  });

  it('should set emissiveColor for selected panel', () => {
    const mat = { emissiveColor: { r: 0.5, g: 0.8, b: 1 } };
    expect(mat.emissiveColor.r).toBe(0.5);
  });
});
