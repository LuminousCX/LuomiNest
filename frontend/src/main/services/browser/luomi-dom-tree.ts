/**
 * LuomiNest 索引化 DOM 树提取脚本。
 *
 * 借鉴 nanobrowser buildDomTree.js 的索引化方案，完全重写实现。
 * 为页面中可见可交互元素注入 data-luomi-index 属性（规避 playwright-highlight-container），
 * 构建精简 DOM 树供 AI 理解页面结构。
 *
 * 用法：通过 webContents.executeJavaScript() 注入 LUOMI_DOM_TREE_SCRIPT 定义全局函数，
 * 然后调用 window.buildLuomiDomTree({ maxDepth, maxElements }) 获取树结构。
 */

/**
 * 注入到页面的脚本字符串。
 * 定义 window.buildLuomiDomTree(args) 全局函数，供后续 executeJavaScript 调用。
 */
export const LUOMI_DOM_TREE_SCRIPT = `
(function() {
  'use strict';

  // 可交互元素标签白名单
  const INTERACTIVE_TAGS = new Set([
    'a', 'button', 'input', 'select', 'textarea', 'summary',
    'details', 'label', 'option', 'optgroup'
  ]);

  // 可交互 role 白名单
  const INTERACTIVE_ROLES = new Set([
    'button', 'link', 'checkbox', 'radio', 'combobox', 'textbox',
    'searchbox', 'listbox', 'menuitem', 'menuitemcheckbox', 'menuitemradio',
    'tab', 'option', 'switch', 'treeitem', 'slider', 'spinbutton'
  ]);

  // 判断元素是否可见
  function isVisible(el) {
    if (!el.isConnected) return false;
    if (el.nodeType !== 1) return false;
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') return false;
    if (parseFloat(style.opacity) === 0) return false;
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) return false;
    return true;
  }

  // 判断元素是否值得索引（可交互或有文本内容）
  function isIndexable(el) {
    if (!isVisible(el)) return false;

    const tag = el.tagName.toLowerCase();
    if (INTERACTIVE_TAGS.has(tag)) return true;

    const role = el.getAttribute('role');
    if (role && INTERACTIVE_ROLES.has(role)) return true;

    // 有 tabindex 的可聚焦元素
    if (el.hasAttribute('tabindex') && el.tabIndex >= 0) return true;

    // 有可点击事件或 contenteditable
    if (el.isContentEditable) return true;

    // 有直接文本内容的容器元素（非内联文本）
    const isInlineText = ['span', 'em', 'strong', 'b', 'i', 'u', 'small', 'sub', 'sup'].includes(tag);
    if (!isInlineText && el.children.length === 0 && el.textContent && el.textContent.trim().length > 0) {
      return true;
    }

    return false;
  }

  // 提取元素的关键属性
  function extractAttrs(el) {
    const attrs = {};
    const importantAttrs = ['id', 'name', 'type', 'value', 'placeholder', 'href', 'src',
                           'role', 'aria-label', 'aria-expanded', 'aria-checked', 'aria-selected',
                           'title', 'alt', 'for', 'data-luomi-index'];

    for (const attr of importantAttrs) {
      const val = el.getAttribute(attr);
      if (val !== null) attrs[attr] = val;
    }
    return attrs;
  }

  // 获取元素的简短文本（截断防 token 爆炸）
  function getText(el, maxLen = 80) {
    const text = (el.innerText || el.textContent || '').trim();
    if (text.length <= maxLen) return text;
    return text.slice(0, maxLen) + '...';
  }

  // 清理旧的索引标记
  function clearOldIndices() {
    const old = document.querySelectorAll('[data-luomi-index]');
    old.forEach(el => el.removeAttribute('data-luomi-index'));
  }

  // 构建节点信息
  function buildNode(el, index) {
    const rect = el.getBoundingClientRect();
    return {
      index: index,
      tag: el.tagName.toLowerCase(),
      role: el.getAttribute('role') || '',
      text: getText(el),
      attrs: extractAttrs(el),
      bounds: {
        x: Math.round(rect.x),
        y: Math.round(rect.y),
        width: Math.round(rect.width),
        height: Math.round(rect.height)
      },
      children: []
    };
  }

  // 主函数：构建索引化 DOM 树
  window.buildLuomiDomTree = function(args) {
    args = args || {};
    const maxDepth = args.maxDepth || 10;
    const maxElements = args.maxElements || 200;

    clearOldIndices();

    let counter = 0;
    const selectorMap = {};

    function walk(el, depth, parentNode) {
      if (counter >= maxElements) return;
      if (depth > maxDepth) return;

      for (const child of el.children) {
        if (counter >= maxElements) break;

        if (isIndexable(child)) {
          counter++;
          child.setAttribute('data-luomi-index', String(counter));
          const node = buildNode(child, counter);
          selectorMap[counter] = {
            tag: node.tag,
            text: node.text,
            bounds: node.bounds
          };
          parentNode.children.push(node);

          // 递归处理子元素
          walk(child, depth + 1, node);
        } else if (isVisible(child)) {
          // 非索引但可见的容器元素，递归向下查找
          walk(child, depth + 1, parentNode);
        }
      }
    }

    const root = {
      index: 0,
      tag: 'document',
      role: '',
      text: document.title || '',
      attrs: { url: location.href },
      bounds: { x: 0, y: 0, width: window.innerWidth, height: window.innerHeight },
      children: []
    };

    walk(document.body, 1, root);

    return {
      tree: root,
      selectorMap: selectorMap,
      totalCount: counter,
      url: location.href,
      title: document.title
    };
  };

  console.info('[LuomiNest] DOM tree builder installed (data-luomi-index)');
})();
`

/**
 * 生成调用 buildLuomiDomTree 的脚本字符串
 * @param maxDepth 最大递归深度（默认 10）
 * @param maxElements 最大索引元素数（默认 200）
 */
export function getDomTreeCallScript(maxDepth: number = 10, maxElements: number = 200): string {
  return `window.buildLuomiDomTree(${JSON.stringify({ maxDepth, maxElements })})`
}
