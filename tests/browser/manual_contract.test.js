const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../../static/main.js'), 'utf8');

function createElement() {
  return {
    style: {}, hidden: false, disabled: false, checked: false, value: '',
    textContent: '', innerHTML: '', files: [], children: [], handlers: {},
    addEventListener(type, handler) { this.handlers[type] = handler; },
    appendChild(child) { this.children.push(child); },
    focus() {},
    getContext() { return { clearRect() {} }; },
  };
}

function createPage(reply) {
  const ids = [
    'uploadForm', 'fileInput', 'manualMode', 'imageMode', 'manualFields',
    'imageFields', 'manualText', 'exampleButton', 'selectedFileName',
    'loading', 'loadingMessage', 'problemTextContainer', 'stepsContainer',
    'instructionsContainer', 'metaContainer', 'animationCanvas', 'controls',
    'playBtn', 'pauseBtn', 'replayBtn', 'errorBox',
  ];
  const elements = Object.fromEntries(ids.map((id) => [id, createElement()]));
  const submitButton = createElement();
  elements.uploadForm.querySelector = () => submitButton;
  elements.manualMode.checked = true;

  class TestFormData {
    constructor() { this.values = new Map(); }
    append(key, value) { this.values.set(key, value); }
    get(key) { return this.values.get(key) ?? null; }
  }

  const requests = [];
  const animations = [];
  class TestAnimationEngine {
    constructor() { animations.push(this); }
    loadInstructions(data) { this.data = data; }
    play() { this.played = true; }
    pause() {}
    destroy() {}
    reset() {}
  }

  vm.runInNewContext(source, {
    document: {
      getElementById: (id) => elements[id],
      createElement,
      createTextNode: (text) => ({ textContent: text }),
    },
    FormData: TestFormData,
    AnimationEngine: TestAnimationEngine,
    fetch: async (url, options) => {
      requests.push({ url, ...options });
      return reply();
    },
    console: { log() {}, error() {} },
  });

  return {
    elements, requests, animations,
    submit: () => elements.uploadForm.handlers.submit({ preventDefault() {} }),
  };
}

const success = {
  problem_type: 'horizontal_projectile',
  problem_text: '一个物体从8米高的平台以10m/s的速度水平抛出，g=9.8m/s²，求运动轨迹。',
  solution_steps: ['识别运动类型', '计算运动轨迹'],
  animation_instructions: { type: 'projectile', initial_speed: 10, angle: 0 },
};

test('manual mode sends only manual_text and renders the canonical response', async () => {
  const page = createPage(() => ({ ok: true, json: async () => success }));
  assert.equal(page.elements.imageFields.hidden, true);
  page.elements.exampleButton.handlers.click();
  assert.equal(page.elements.manualText.value, success.problem_text);

  await page.submit();

  assert.equal(page.requests.length, 1);
  assert.equal(page.requests[0].url, '/upload');
  assert.equal(page.requests[0].body.get('manual_text'), success.problem_text);
  assert.equal(page.requests[0].body.get('file'), null);
  assert.equal(page.elements.problemTextContainer.textContent, success.problem_text);
  assert.equal(page.elements.stepsContainer.children[0].children.length, 2);
  assert.equal(page.animations[0].played, true);
});

test('image mode sends only file and shows the server error message', async () => {
  const page = createPage(() => ({
    ok: false, status: 500,
    json: async () => ({ message: '处理失败', suggestion: '请配置 Claude API Key' }),
  }));
  page.elements.manualMode.checked = false;
  page.elements.imageMode.checked = true;
  page.elements.imageMode.handlers.change();
  const file = { name: 'problem.png' };
  page.elements.fileInput.files = [file];

  await page.submit();

  assert.equal(page.elements.manualFields.hidden, true);
  assert.equal(page.requests[0].body.get('file'), file);
  assert.equal(page.requests[0].body.get('manual_text'), null);
  assert.match(page.elements.errorBox.textContent, /处理失败.*请配置 Claude API Key/);
});

test('empty manual text stays in the browser and never sends a request', async () => {
  const page = createPage(() => { throw new Error('fetch should not run'); });
  await page.submit();
  assert.equal(page.requests.length, 0);
  assert.match(page.elements.errorBox.textContent, /请输入物理题目/);
});
