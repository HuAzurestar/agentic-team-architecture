export const MODES = {
  search: { label: '内容搜索', path: '/agentmemory/search', hint: '搜索会话观察记录和长期记忆，返回相关内容。', placeholder: '例如：PIRC-17 论文结构，或某个文件名' },
  smart: { label: '智能搜索', path: '/agentmemory/smart-search', hint: '先查看标题，再按需展开少量命中。', placeholder: '输入主题、关键词或一段问题' },
  lessons: { label: '经验教训', path: '/agentmemory/lessons/search', hint: '搜索保存的经验、用户纠正和工作规则。', placeholder: '例如：检索策略、代码审查、用户偏好' },
  insights: { label: '归纳洞见', path: '/agentmemory/insights/search', hint: '搜索从记忆中归纳出的结论。', placeholder: '例如：性能 缓存，使用两个以上字符的词' },
  vision: { label: '图片搜索', path: '/agentmemory/vision-search', hint: '按描述或参考图片搜索截图，需要服务端启用图片向量。', placeholder: '例如：带有错误提示的登录页面' },
};

export const DEFAULTS = {
  baseUrl: 'http://127.0.0.1:3111', token: '', rememberToken: true, compatibility: 'local',
  mode: 'search', project: '', agentId: '', sessionId: '', limit: 5, format: 'narrative',
  tokenBudget: 1800, minConfidence: 0.1, targetLayer: 'all', includeLessons: true,
  imageRef: '', drafts: {}, history: [],
};

export function buildBody(mode, state, imageBase64 = '') {
  const query = (state.drafts[mode] || '').trim();
  const body = {};
  const limit = Number(state.limit);
  if (!Number.isInteger(limit) || limit < 1 || limit > 100) throw new Error('返回条数需为 1～100 的整数。');
  if (mode !== 'vision' && !query) throw new Error('请先输入搜索内容。');
  if (mode === 'vision') {
    if (imageBase64) body.queryImageBase64 = imageBase64;
    else if (query) body.queryText = query;
    else if (state.imageRef.trim()) body.queryImageRef = state.imageRef.trim();
    else throw new Error('请输入图片描述、选择参考图片或填写图片引用。');
    body.topK = Math.min(50, limit);
    if (state.sessionId.trim()) body.sessionId = state.sessionId.trim();
    return body;
  }
  body.query = query;
  body.limit = limit;
  if (state.project.trim()) body.project = state.project.trim();
  if (mode === 'lessons' || mode === 'insights') {
    const confidence = Number(state.minConfidence);
    if (!Number.isFinite(confidence) || confidence < 0 || confidence > 1) throw new Error('最低置信度需在 0～1 之间。');
    body.minConfidence = confidence;
  } else {
    if (state.agentId.trim()) body.agentId = state.agentId.trim();
    if (state.compatibility === 'latest') body.targetLayer = state.targetLayer;
    if (mode === 'search') {
      body.format = state.format;
      const budget = Number(state.tokenBudget);
      if (!Number.isInteger(budget) || budget < 1) throw new Error('结果预算需为正整数。');
      body.token_budget = budget;
    } else body.includeLessons = state.includeLessons;
  }
  return body;
}

export function persistable(state) {
  return { ...state, token: state.rememberToken ? state.token : '', history: state.history.slice(0, 15) };
}

export function restoreState(raw) {
  try {
    const saved = JSON.parse(raw || '{}');
    const state = { ...DEFAULTS };
    for (const key of Object.keys(DEFAULTS)) {
      if (key in saved && typeof saved[key] === typeof DEFAULTS[key]) state[key] = saved[key];
    }
    state.drafts = saved.drafts && typeof saved.drafts === 'object' && !Array.isArray(saved.drafts)
      ? Object.fromEntries(Object.entries(saved.drafts).filter(([key, value]) => key in MODES && typeof value === 'string')) : {};
    state.history = Array.isArray(saved.history) ? saved.history.filter(item => item && item.mode in MODES && typeof item.query === 'string').slice(0, 15) : [];
    if (!(state.mode in MODES)) state.mode = 'search';
    if (!['local', 'latest'].includes(state.compatibility)) state.compatibility = 'local';
    if (!state.rememberToken) state.token = '';
    return state;
  } catch { return { ...DEFAULTS, drafts: {}, history: [] }; }
}

export function resultRows(data) {
  if (!data || typeof data !== 'object') return [];
  const items = data.results || data.observations || data.insights || data.lessons || [];
  if (!Array.isArray(items)) return [];
  return items.map(item => {
    const record = item.observation || item;
    return {
      raw: item,
      title: record.title || record.content?.slice(0, 100) || record.imageRef || '未命名记录',
      content: record.narrative || record.content || '',
      obsId: item.obsId || record.id || record.observationId,
      sessionId: item.sessionId || record.sessionId,
      layer: item.layer || record.type || (record.imageRef ? 'image' : record.id?.startsWith('lsn_') ? 'lesson' : record.id?.startsWith('ins_') ? 'insight' : ''),
      score: item.score ?? record.score,
      confidence: record.confidence,
      timestamp: record.timestamp || record.createdAt || record.updatedAt,
    };
  });
}
