const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const context = vm.createContext({ window: {}, console: { log() {} } });
for (const file of ['animations/animation_base.js', 'animations/projectile_motion.js',
  'animations/free_fall.js', 'animations/uniform.js', 'animations/uniform_acceleration.js',
  'animations/uniform_circular.js', 'animations/physics_visualizer.js', 'static/animation.js']) {
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../..', file), 'utf8'), context);
}
const normalize = context.window.AnimationEngine.normalizePayload;
const canvas = { width: 720, height: 420, getContext: () => ({}) };
context.canvas = canvas;
context.HTMLCanvasElement = class {
  constructor() { this.width = 720; this.height = 420; }
  getContext() { return new Proxy({}, { get: () => () => {} }); }
  dispatchEvent() {}
};
context.CustomEvent = class {};
context.Event = class {};
context.requestAnimationFrame = () => 1;
context.cancelAnimationFrame = () => {};
const complete = { type: 'projectile', initial_speed: 20, angle: 45, gravity: 9.8, initial_y: 0, duration: 3 };

test('required parameters cannot be supplied by the adapter', () => {
  for (const field of ['initial_speed', 'angle', 'gravity', 'initial_y']) {
    const raw = { ...complete }; delete raw[field];
    assert.throws(() => normalize(raw), /物理参数/);
  }
  for (const raw of [[], {}, { ...complete, type: 'inclined_plane' }, { type: 'uniform_acceleration' }, { type: 'uniform_circular' }]) {
    assert.throws(() => normalize(raw));
  }
  assert.equal(normalize(null), null);
});

test('zero speed, angle and height reach the actual projectile renderer unchanged', () => {
  const data = normalize({ ...complete, initial_speed: 0, angle: 0, initial_y: 0 });
  context.params = data.parameters;
  const animation = vm.runInContext('new ProjectileMotion(canvas, params)', context);
  assert.equal(animation.v0, 0);
  assert.equal(animation.angle, 0);
  assert.equal(animation.h0, 0);
  assert.equal(animation.t_land, 0);
  assert.equal(animation.mass, null);
  assert.equal(animation.getPhysicsValues().gForce, 'N/A');
});

test('free fall with zero height keeps it; omitted height or restitution fails', () => {
  context.params = normalize({ ...complete, type: 'free_fall', initial_speed: 0 }).parameters;
  const animation = vm.runInContext('new FreeFall(canvas, params)', context);
  assert.equal(animation.h0, 0);
  assert.equal(animation.bounce, false);
  assert.throws(() => normalize({ type: 'free_fall', gravity: 9.8 }));
  context.params = { ...context.params, bounce: true };
  assert.throws(() => vm.runInContext('new FreeFall(canvas, params)', context), /bounceLoss/);
});

test('new-format payloads and direct constructors also reject missing values', () => {
  assert.throws(() => normalize({ sub_type: 'projectile_motion', parameters: {} }));
  context.params = {};
  for (const type of ['ProjectileMotion', 'FreeFall', 'Uniform', 'UniformAcceleration', 'UniformCircular']) {
    assert.throws(() => vm.runInContext(`new ${type}(canvas, params)`, context), /物理参数/);
  }
  const visualizer = Object.create(context.window.PhysicsVisualizer.prototype);
  assert.throws(() => visualizer.loadAnimation({ sub_type: 'unknown', parameters: {} }), /不支持/);
});

test('uniform motion has no invented zero gravity or unlimited zero-duration playback', () => {
  context.params = normalize({ ...complete, type: 'uniform', initial_speed: 0, angle: 0, gravity: null, duration: 0 }).parameters;
  const animation = vm.runInContext('new Uniform(canvas, params)', context);
  assert.equal(animation.g, null);
  assert.equal(animation.getPhysicsValues().gForce, 'N/A');
  animation.update(1 / 60);
  assert.equal(animation.isEnded, true);
});

test('zero friction and explicit circular phase are preserved', () => {
  context.params = { radius: 2, omega: 0, mass: 1, mu: 0, g: 9.8, initialAngle: 0, duration: 0, centerX: 0, centerY: 0 };
  const animation = vm.runInContext('new UniformCircular(canvas, params)', context);
  assert.equal(animation.mu, 0);
  assert.equal(animation.center.x, 0);
  context.params.omega = 5;
  assert.throws(() => vm.runInContext('new UniformCircular(canvas, params)', context), /超过/);
});

test('the full adapter and visualizer load valid data and apply display scale', () => {
  const realCanvas = new context.HTMLCanvasElement();
  const engine = new context.window.AnimationEngine(realCanvas);
  engine.loadInstructions({ ...complete, scale: 20 });
  assert.equal(engine.visualizer.currentAnimation.config.scale, 20);
  engine.visualizer.currentAnimation.draw();
  engine.loadInstructions({ ...complete, type: 'free_fall', initial_speed: 0, initial_y: 20, scale: 16 });
  const animation = engine.visualizer.currentAnimation;
  assert.equal(animation.h0, 20);
  assert.equal(animation.checkBoundary(), false);
  animation.draw();
});

test('the existing merge console test passes against the real renderer classes', async () => {
  context.document = { createElement: () => new context.HTMLCanvasElement(), body: { appendChild() {}, removeChild() {} } };
  context.console.error = () => {};
  context.setTimeout = callback => setTimeout(callback, 1);
  const result = await vm.runInContext(fs.readFileSync(path.join(__dirname, 'test_animation_merge.js'), 'utf8'), context);
  assert.equal(result.success, true, JSON.stringify(result.results));
});
