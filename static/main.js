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
const assumptionsContainer = document.getElementById('assumptionsContainer');
const warningsContainer = document.getElementById('warningsContainer');
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

function renderPhysicsNotes(assumptions, warnings) {
  for (const [container, entries, empty] of [
    [assumptionsContainer, assumptions.map(a => `${a.parameter} = ${a.value}：${a.reason}`), '无额外参数假设。'],
    [warningsContainer, warnings, '无警告。'],
  ]) {
    container.innerHTML = '';
    if (!entries.length) {
      container.textContent = empty;
      continue;
    }
    const list = document.createElement('ul');
    entries.forEach(entry => {
      const item = document.createElement('li');
      item.textContent = entry;
      list.appendChild(item);
    });
    container.appendChild(list);
  }
}

function renderInstructions(rawInstructions) {
  instructionsContainer.innerHTML = '';
  if (!rawInstructions) {
    instructionsContainer.textContent = '未生成动画，请查看警告并补充必要条件。';
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
  return raw && typeof raw === 'object' && !Array.isArray(raw) ? raw : null;
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
  assumptionsContainer.textContent = '';
  warningsContainer.textContent = '';

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
        !Array.isArray(data.assumptions) ||
        !data.assumptions.every(a => a && typeof a.parameter === 'string' && 'value' in a && typeof a.reason === 'string') ||
        !Array.isArray(data.warnings) || !data.warnings.every(w => typeof w === 'string') ||
        (data.animation_instructions != null &&
          (typeof data.animation_instructions !== 'object' || Array.isArray(data.animation_instructions)))) {
      throw new Error('服务器响应格式不正确，请检查后端日志。');
    }

    renderProblemText(data.problem_text);
    renderSteps(data.solution_steps);
    renderInstructions(data.animation_instructions);
    renderMeta(data);
    renderPhysicsNotes(data.assumptions, data.warnings);

    const animationData = normalizeAnimationData(data.animation_instructions);
    if (!animationData || data.warnings.length) {
      if (!data.warnings.length) showError('后端未返回可用的动画数据，已跳过动画演示。');
      return;
    }

    try {
      // 单例模式：首次创建，后续重用
      if (!engine) {
        engine = new AnimationEngine(canvas);
      } else {
        engine.destroy();
      }
      engine.loadInstructions(animationData);
      bindControls(engine);
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
