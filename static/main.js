const uploadForm = document.getElementById('uploadForm');
const fileInput = document.getElementById('fileInput');
const manualMode = document.getElementById('manualMode');
const imageMode = document.getElementById('imageMode');
const manualFields = document.getElementById('manualFields');
const imageFields = document.getElementById('imageFields');
const manualText = document.getElementById('manualText');
const exampleButton = document.getElementById('exampleButton');
const selectedFileName = document.getElementById('selectedFileName');
const loadingEl = document.getElementById('loading');
const loadingMessage = document.getElementById('loadingMessage');
const problemTextContainer = document.getElementById('problemTextContainer');
const stepsContainer = document.getElementById('stepsContainer');
const instructionsContainer = document.getElementById('instructionsContainer');
const metaContainer = document.getElementById('metaContainer');
const canvas = document.getElementById('animationCanvas');
const controls = document.getElementById('controls');
const playBtn = document.getElementById('playBtn');
const pauseBtn = document.getElementById('pauseBtn');
const replayBtn = document.getElementById('replayBtn');
const errorBox = document.getElementById('errorBox');

let engine = null;
const submitButton = uploadForm.querySelector('button[type="submit"]');

controls.style.display = 'none';

function syncInputMode() {
  const isManual = manualMode.checked;
  manualFields.hidden = !isManual;
  imageFields.hidden = isManual;
  manualText.disabled = !isManual;
  fileInput.disabled = isManual;
  submitButton.textContent = isManual ? '解析文字并生成动画' : '上传图片并生成动画';
  showError('');
}

manualMode.addEventListener('change', syncInputMode);
imageMode.addEventListener('change', syncInputMode);
exampleButton.addEventListener('click', () => {
  manualText.value = '一个物体从8米高的平台以10m/s的速度水平抛出，g=9.8m/s²，求运动轨迹。';
  manualText.focus();
});
fileInput.addEventListener('change', () => {
  selectedFileName.textContent = fileInput.files[0]?.name || '';
});
syncInputMode();

function setLoading(isLoading) {
  loadingEl.style.display = isLoading ? 'flex' : 'none';
  submitButton.disabled = isLoading;
}

function showError(message) {
  if (!message) {
    errorBox.style.display = 'none';
    errorBox.textContent = '';
    return;
  }
  errorBox.textContent = message;
  errorBox.style.display = 'block';
}

function renderProblemText(problemText) {
  problemTextContainer.textContent = problemText || '未获取到题目文本。';
}

function renderSteps(steps) {
  stepsContainer.innerHTML = '';
  if (!steps || !Array.isArray(steps) || steps.length === 0) {
    stepsContainer.textContent = '未获取到解题步骤。';
    return;
  }
  const ol = document.createElement('ol');
  steps.forEach((step) => {
    const li = document.createElement('li');
    li.textContent = typeof step === 'string' ? step : JSON.stringify(step);
    ol.appendChild(li);
  });
  stepsContainer.appendChild(ol);
}

function renderInstructions(rawInstructions) {
  instructionsContainer.innerHTML = '';
  if (!rawInstructions) {
    instructionsContainer.textContent = '暂无动画指令';
    return;
  }

  if (Array.isArray(rawInstructions)) {
    const ul = document.createElement('ul');
    rawInstructions.forEach((item) => {
      const li = document.createElement('li');
      li.textContent = typeof item === 'string' ? item : JSON.stringify(item, null, 2);
      ul.appendChild(li);
    });
    instructionsContainer.appendChild(ul);
  } else if (typeof rawInstructions === 'object') {
    const pre = document.createElement('pre');
    pre.textContent = JSON.stringify(rawInstructions, null, 2);
    instructionsContainer.appendChild(pre);
  } else {
    instructionsContainer.textContent = String(rawInstructions);
  }
}

function renderMeta(data) {
  metaContainer.innerHTML = '';
  const list = document.createElement('ul');

  const items = [
    ['题目类型', data.problem_type || '未知'],
  ];

  if (data.parameters && typeof data.parameters === 'object') {
    items.push(['参数', JSON.stringify(data.parameters, null, 2)]);
  }

  items.forEach(([label, value]) => {
    const li = document.createElement('li');
    const strong = document.createElement('strong');
    strong.textContent = `${label}：`;
    li.appendChild(strong);
    li.appendChild(document.createTextNode(value));
    list.appendChild(li);
  });
  metaContainer.appendChild(list);
}

function normalizeAnimationData(raw) {
  if (!raw) return null;

  if (Array.isArray(raw)) {
    // 占位数组场景：使用一个默认的抛体运动示例，确保画布可演示
    return {
      type: 'projectile',
      initial_speed: 18,
      angle: 55,
      gravity: 9.8,
      initial_x: 0,
      initial_y: 0,
      scale: 24,
      duration: 4,
    };
  }

  if (typeof raw === 'object') {
    // 如果是对象，直接返回用于动画解析
    return raw;
  }

  return null;
}

function bindControls(currentEngine) {
  controls.style.display = 'flex';
  playBtn.onclick = () => currentEngine.play();
  pauseBtn.onclick = () => currentEngine.pause();
  replayBtn.onclick = () => {
    currentEngine.reset();
    currentEngine.play();
  };
}

function resetCanvas() {
  if (engine) {
    engine.pause();
  }
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  controls.style.display = 'none';
}

uploadForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const formData = new FormData();
  if (manualMode.checked) {
    const text = manualText.value.trim();
    if (!text) {
      showError('请输入物理题目，或点击“填入示例题目”。');
      return;
    }
    formData.append('manual_text', text);
    loadingMessage.textContent = '正在用规则解析题目，请稍候...';
  } else {
    const file = fileInput.files[0];
    if (!file) {
      showError('请选择一张 PNG 或 JPG 图片再上传。');
      return;
    }
    formData.append('file', file);
    loadingMessage.textContent = '正在调用 Claude 解析图片，请稍候...';
  }

  showError('');
  setLoading(true);
  resetCanvas();
  problemTextContainer.textContent = '';
  stepsContainer.textContent = '';
  instructionsContainer.textContent = '';
  metaContainer.textContent = '';

  try {
    const response = await fetch('/upload', { method: 'POST', body: formData });
    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error(`服务器返回无法读取的响应（HTTP ${response.status}）。`);
    }
    if (!response.ok) {
      throw new Error([data.message || `请求失败（HTTP ${response.status}）`, data.suggestion].filter(Boolean).join('。'));
    }
    if (!data || typeof data.problem_text !== 'string' ||
        typeof data.problem_type !== 'string' ||
        !Array.isArray(data.solution_steps) ||
        !data.animation_instructions ||
        typeof data.animation_instructions !== 'object' ||
        Array.isArray(data.animation_instructions)) {
      throw new Error('服务器响应格式不正确，请检查后端日志。');
    }

    renderProblemText(data.problem_text);
    renderSteps(data.solution_steps);
    renderInstructions(data.animation_instructions);
    renderMeta(data);

    const animationData = normalizeAnimationData(data.animation_instructions);
    if (!animationData) {
      showError('后端未返回可用的动画数据，已跳过动画演示。');
      return;
    }

    try {
      // 单例模式：首次创建，后续重用
      if (!engine) {
        engine = new AnimationEngine(canvas);
        bindControls(engine);
      } else {
        engine.destroy();
      }
      engine.loadInstructions(animationData);
      engine.play();
    } catch (err) {
      console.error('动画初始化失败:', err);
      showError(`动画初始化失败：${err.message}`);
    }
  } catch (error) {
    console.error(error);
    showError(`解析失败：${error.message}`);
  } finally {
    setLoading(false);
  }
});
