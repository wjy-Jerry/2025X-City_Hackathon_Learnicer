// ═══════════════════════════════════════════════════════════════
// 🚀 一键前端测试脚本
// ═══════════════════════════════════════════════════════════════
// 复制整个文件内容，粘贴到浏览器控制台 (F12 → Console)，回车即可运行
// ═══════════════════════════════════════════════════════════════

(async function quickTest() {
  console.clear();
  console.log('%c🎬 物理题可视化前端测试', 'font-size: 20px; font-weight: bold; color: #4CAF50');
  console.log('═══════════════════════════════════════════════════════════════\n');

  // 测试 1: 验证页面元素
  console.log('📋 测试 1: 检查页面元素...');
  const canvas = document.getElementById('animationCanvas');
  const controls = document.getElementById('controls');
  const stepsContainer = document.getElementById('stepsContainer');

  if (!canvas) {
    console.error('❌ 找不到 Canvas 元素');
    return;
  }
  console.log('✅ Canvas 元素存在');
  console.log(`   尺寸: ${canvas.width} x ${canvas.height}`);

  if (!controls) {
    console.error('❌ 找不到控制按钮');
    return;
  }
  console.log('✅ 控制按钮存在\n');

  // 测试 2: 直接播放动画（无需后端）
  console.log('🎨 测试 2: 直接播放平抛运动动画...');

  const animationData = {
    type: 'projectile',
    initial_speed: 10,
    angle: 0,
    gravity: 9.8,
    initial_x: 0,
    initial_y: 8,
    duration: 1.28,
    scale: 30
  };

  try {
    const engine = new AnimationEngine(canvas);
    engine.loadInstructions(animationData);
    engine.play();

    // 显示控制按钮
    controls.style.display = 'flex';
    document.getElementById('playBtn').onclick = () => {
      engine.play();
      console.log('▶️  播放');
    };
    document.getElementById('pauseBtn').onclick = () => {
      engine.pause();
      console.log('⏸  暂停');
    };
    document.getElementById('replayBtn').onclick = () => {
      engine.reset();
      engine.play();
      console.log('🔄 重播');
    };

    console.log('✅ 动画已开始播放');
    console.log('   类型: 平抛运动');
    console.log('   初速度: 10 m/s');
    console.log('   高度: 8 m');
    console.log('   持续时间: 1.28 秒\n');

    // 等待 2 秒后继续
    await new Promise(resolve => setTimeout(resolve, 2000));

  } catch (error) {
    console.error('❌ 动画播放失败:', error);
    return;
  }

  // 测试 3: 测试后端 API
  console.log('🌐 测试 3: 测试后端 API 集成...');

  const testQuestion = '一个物体从8米高的平台以10m/s的速度水平抛出，重力加速度g=9.8m/s²，求物体的运动轨迹。';

  try {
    const formData = new FormData();
    formData.append('manual_text', testQuestion);

    console.log('   发送请求到 /upload...');
    const response = await fetch('/upload', {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    renderPhysicsNotes(data.assumptions || [], data.warnings || []);
    if (!data.animation_instructions || data.warnings?.length) {
      console.warn('未生成动画：', data.warnings);
      return;
    }
    console.log('✅ 后端响应成功');
    console.log('   题目类型:', data.problem_type);
    console.log('   运动类型:', data.parameters?.motion_type);
    console.log('   解题步骤数量:', data.solution_steps?.length);

    // 渲染解题步骤
    if (stepsContainer) {
      stepsContainer.innerHTML = '<ol>' +
        data.solution_steps.map(s => `<li>${s}</li>`).join('') +
        '</ol>';
      console.log('✅ 解题步骤已渲染到页面');
    }

    // 渲染动画指令
    const instructionsContainer = document.getElementById('instructionsContainer');
    if (instructionsContainer) {
      instructionsContainer.innerHTML =
        `<pre>${JSON.stringify(data.animation_instructions, null, 2)}</pre>`;
      console.log('✅ 动画指令已渲染到页面');
    }

    // 播放新动画
    const newEngine = new AnimationEngine(canvas);
    newEngine.loadInstructions(data.animation_instructions);
    newEngine.play();
    console.log('✅ 后端返回的动画已开始播放\n');

  } catch (error) {
    console.error('❌ 后端 API 测试失败:', error);
    console.log('💡 请确认后端正在运行: http://127.0.0.1:5000/health\n');
  }

  // 测试总结
  console.log('═══════════════════════════════════════════════════════════════');
  console.log('%c🎉 测试完成！', 'font-size: 18px; font-weight: bold; color: #2196F3');
  console.log('═══════════════════════════════════════════════════════════════');
  console.log('\n💡 下一步:');
  console.log('   1. 观察 Canvas 动画是否正常播放');
  console.log('   2. 测试控制按钮（播放/暂停/重播）');
  console.log('   3. 查看左侧解题步骤和动画指令');
  console.log('   4. 尝试上传物理题图片');
  console.log('\n📖 详细测试: 在控制台运行以下命令');
  console.log('   const script = document.createElement("script");');
  console.log('   script.src = "/static/test-frontend.js";');
  console.log('   document.head.appendChild(script);');
  console.log('   // 然后运行: PhysicsTestSuite.help()');
  console.log('\n═══════════════════════════════════════════════════════════════\n');

})();