/**
 * AnimationEngine - 兼容适配层
 *
 * 职责：将 A 同学的旧接口映射到 animations/ 文件夹的新实现（C 同学版本）
 *
 * 旧接口（保留向后兼容）：
 *   - new AnimationEngine(canvas)
 *   - engine.loadInstructions(data)
 *   - engine.play() / pause() / reset()
 *
 * 新实现（内部使用 PhysicsVisualizer）：
 *   - animations/physics_visualizer.js
 *   - animations/animation_base.js
 *   - animations/projectile_motion.js
 *   - animations/free_fall.js
 */

class AnimationEngine {
  constructor(canvas) {
    if (!canvas) {
      throw new Error('Canvas 元素不存在');
    }
    this.canvas = canvas;

    // 内部使用 PhysicsVisualizer（C 同学的核心引擎）
    this.visualizer = new PhysicsVisualizer(canvas, {});

    // 保留旧接口的状态（用于兼容性）
    this.isPlaying = false;
  }

  /**
   * 数据格式标准化：旧格式 → 新格式
   *
   * 旧格式（A 同学）：
   * {
   *   type: 'projectile',
   *   initial_speed: 16,
   *   angle: 50,
   *   gravity: 9.8,
   *   initial_x: 0,
   *   initial_y: 0,
   *   scale: 22,
   *   duration: 4
   * }
   *
   * 新格式（C 同学）：
   * {
   *   sub_type: 'projectile_motion',
   *   parameters: {
   *     v0: 20,
   *     angle: 45,
   *     g: 9.8,
   *     h0: 0,
   *     mass: 1
   *   },
   *   solution_steps: [...]
   * }
   */
  static normalizePayload(raw) {
    if (raw == null) return null;
    if (typeof raw !== 'object' || Array.isArray(raw)) throw new Error('动画必须为参数对象，不能用示例替代。');
    if (raw.animation) return AnimationEngine.normalizePayload(raw.animation);
    const type = raw.sub_type ?? raw.motion_type_original ?? raw.type;
    const aliases = { projectile: 'projectile_motion', horizontal_projectile: 'projectile_motion', vertical_throw: 'projectile_motion' };
    const subType = aliases[type] ?? type;
    const required = {
      projectile_motion: ['v0', 'angle', 'g', 'h0'],
      free_fall: ['h0', 'g'],
      uniform: ['vx', 'vy', 'x0', 'y0', 'duration'],
      uniform_acceleration: ['F', 'mu', 'mass', 'g', 'x0', 'v0', 'duration'],
      uniform_circular: ['radius', 'omega', 'mass', 'mu', 'g', 'initialAngle', 'duration'],
    };
    if (!required[subType]) throw new Error(`不支持的运动类型：${type ?? '未指定'}。`);
    let parameters;
    if (raw.sub_type) {
      parameters = { ...raw.parameters };
      if (subType === 'free_fall') parameters.h0 = parameters.h0 ?? parameters.height;
    } else {
      const v0 = raw.initial_speed ?? raw.v0;
      const angle = raw.angle;
      const g = raw.gravity ?? raw.g;
      const h0 = raw.initial_y ?? raw.y0 ?? raw.h0;
      parameters = { v0, angle, g, h0, mass: raw.mass ?? null, duration: raw.duration };
      if (subType === 'free_fall') {
        parameters.bounce = raw.bounce === true;
        parameters.bounceLoss = raw.bounceLoss;
      } else if (subType === 'uniform') {
        AnimationBase.validateParameters({ v0, angle }, ['v0', 'angle']);
        parameters.vx = v0 * Math.cos(angle * Math.PI / 180);
        parameters.vy = v0 * Math.sin(angle * Math.PI / 180);
        parameters.x0 = raw.initial_x ?? 0; // Coordinate origin, not an invented travel distance.
        parameters.y0 = h0;
      } else if (subType === 'uniform_acceleration') {
        Object.assign(parameters, { F: raw.F, mu: raw.mu, x0: raw.initial_x ?? 0 });
      } else if (subType === 'uniform_circular') {
        Object.assign(parameters, { radius: raw.radius, omega: raw.omega, mu: raw.mu,
          initialAngle: raw.initialAngle, centerX: raw.centerX, centerY: raw.centerY });
      }
    }
    AnimationBase.validateParameters(parameters, required[subType],
      subType === 'uniform' ? [] : subType === 'uniform_circular' ? ['g', 'mass', 'radius'] : ['g']);
    if (subType === 'free_fall' && parameters.v0 != null && parameters.v0 !== 0) {
      throw new Error('自由落体必须从静止释放。');
    }
    return { sub_type: subType, parameters, scale: raw.scale };
  }

  /**
   * 加载动画指令（旧接口）
   * @param {Object|Array} data - 动画数据（自动转换格式）
   */
  loadInstructions(data) {
    const normalized = AnimationEngine.normalizePayload(data);
    if (!normalized) {
      throw new Error('动画指令为空或格式不支持');
    }

    console.log('[兼容层] 旧格式 → 新格式转换:', {
      原始数据: data,
      转换后: normalized
    });

    // 调用 PhysicsVisualizer.loadAnimation()
    this.visualizer.loadAnimation(normalized);
  }

  /**
   * 播放动画
   */
  play() {
    this.isPlaying = true;
    this.visualizer.play();
  }

  /**
   * 暂停动画
   */
  pause() {
    this.isPlaying = false;
    this.visualizer.pause();
  }

  /**
   * 重置动画
   */
  reset() {
    this.isPlaying = false;
    this.visualizer.reset();
  }

  /**
   * 调整画布尺寸（可选功能）
   */
  resize(width, height) {
    if (width && height) {
      this.canvas.width = width;
      this.canvas.height = height;
    }
  }

  /**
   * 销毁动画引擎（可选功能）
   */
  destroy() {
    this.pause();
    if (this.visualizer.currentAnimation) {
      this.visualizer.currentAnimation.pause();
    }
  }
}

// 全局导出（确保兼容性）
if (typeof window !== 'undefined') {
  window.AnimationEngine = AnimationEngine;
}