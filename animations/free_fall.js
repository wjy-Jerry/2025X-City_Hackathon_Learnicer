class FreeFall extends AnimationBase {
  constructor(canvas, params) {
    super(canvas);
    // 兼容性：支持 height 或 h0
    params = { ...params, h0: params.h0 ?? params.height };
    AnimationBase.validateParameters(params, ['h0', 'g'], ['g']);
    if (params.v0 != null && params.v0 !== 0) throw new Error('自由落体必须从静止释放。');
    this.h0 = params.h0;
    this.g = params.g;
    this.mass = params.mass ?? null;
    this.bounce = params.bounce === true;
    if (this.bounce && (!Number.isFinite(params.bounceLoss) || params.bounceLoss < 0 || params.bounceLoss > 1)) {
      throw new Error('反弹动画必须明确提供 0 到 1 之间的 bounceLoss。');
    }
    this.bounceLoss = params.bounceLoss;
    this.showVelocity = params.showVelocity || true;
    this.showAcceleration = params.showAcceleration || false;
    
    this.init();
  }
  
  init() {
    this.objects = [{
      position: { x: 5, y: this.h0 },  // x位置调整为5，避免靠边
      velocity: { x: 0, y: 0 },
      acceleration: { x: 0, y: -this.g },
      shape: 'circle',
      radius: 10,
      mass: this.mass,
      color: 'red'
    }];
    
    this.trail = [];
    this.time = 0;
    this.isEnded = false;
  }
  
  update(dt) {
    if (this.isEnded) return;
    
    const obj = this.objects[0];
    
    // 更新速度
    obj.velocity.y += obj.acceleration.y * dt;
    
    // 更新位置
    obj.position.y += obj.velocity.y * dt;
    
    // 记录轨迹
    if (this.time % 0.1 < dt) {
      this.trail.push({ x: obj.position.x, y: obj.position.y });
    }
    
    // 落地检测
    if (obj.position.y <= 0) {
      obj.position.y = 0;
      if (this.bounce && Math.abs(obj.velocity.y) > 0.5) {
        obj.velocity.y = -obj.velocity.y * this.bounceLoss;
      } else {
        obj.velocity.y = 0;
        this.isEnded = true;  // 停止运动
      }
    }
  }
  
  draw() {
    super.draw();
    // 修改：移除旧的 showAcceleration 绘制，由 super 处理
  }
}