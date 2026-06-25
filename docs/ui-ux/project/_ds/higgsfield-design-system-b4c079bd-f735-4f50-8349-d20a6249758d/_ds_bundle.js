/* @ds-bundle: {"format":3,"namespace":"HiggsfieldDesignSystem_b4c079","components":[{"name":"Avatar","sourcePath":"components/core/Avatar.jsx"},{"name":"Badge","sourcePath":"components/core/Badge.jsx"},{"name":"Button","sourcePath":"components/core/Button.jsx"},{"name":"IconButton","sourcePath":"components/core/IconButton.jsx"},{"name":"Spinner","sourcePath":"components/core/Spinner.jsx"},{"name":"Tag","sourcePath":"components/core/Tag.jsx"},{"name":"Dialog","sourcePath":"components/feedback/Dialog.jsx"},{"name":"Toast","sourcePath":"components/feedback/Toast.jsx"},{"name":"ToastStack","sourcePath":"components/feedback/Toast.jsx"},{"name":"Tooltip","sourcePath":"components/feedback/Tooltip.jsx"},{"name":"Input","sourcePath":"components/forms/Input.jsx"},{"name":"SegmentedControl","sourcePath":"components/forms/SegmentedControl.jsx"},{"name":"Select","sourcePath":"components/forms/Select.jsx"},{"name":"Slider","sourcePath":"components/forms/Slider.jsx"},{"name":"Switch","sourcePath":"components/forms/Switch.jsx"},{"name":"Card","sourcePath":"components/media/Card.jsx"},{"name":"MediaCard","sourcePath":"components/media/MediaCard.jsx"},{"name":"ModelPill","sourcePath":"components/media/ModelPill.jsx"},{"name":"PromptComposer","sourcePath":"components/media/PromptComposer.jsx"}],"sourceHashes":{"components/core/Avatar.jsx":"16d3ce7efb8a","components/core/Badge.jsx":"9699b1a572a4","components/core/Button.jsx":"880d56030591","components/core/IconButton.jsx":"801e44e94515","components/core/Spinner.jsx":"dcc95e83e48d","components/core/Tag.jsx":"323a4106f9b0","components/feedback/Dialog.jsx":"c92f20f434fa","components/feedback/Toast.jsx":"ea6996ea883c","components/feedback/Tooltip.jsx":"281aacea1865","components/forms/Input.jsx":"993462246b72","components/forms/SegmentedControl.jsx":"8e3349da908d","components/forms/Select.jsx":"622e93fabd63","components/forms/Slider.jsx":"ffb0f9ac3a4d","components/forms/Switch.jsx":"8c4845caf261","components/media/Card.jsx":"6acea42168be","components/media/MediaCard.jsx":"7f4bd62dcaa1","components/media/ModelPill.jsx":"43c7431279f1","components/media/PromptComposer.jsx":"434f90c85eaa","ui_kits/web-app/CreateView.jsx":"694f3ec88a06","ui_kits/web-app/ExploreView.jsx":"4eb57492f8bf","ui_kits/web-app/Sidebar.jsx":"bbc6f51f5225","ui_kits/web-app/TopBar.jsx":"43ad03bccc61","ui_kits/web-app/data.js":"2c9eabe4b422","ui_kits/web-app/icons.jsx":"e39caf617391"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.HiggsfieldDesignSystem_b4c079 = window.HiggsfieldDesignSystem_b4c079 || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/core/Avatar.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const CSS = `
.hf-avatar{
  position:relative; display:inline-flex; align-items:center; justify-content:center;
  width:36px; height:36px; border-radius:var(--hf-radius-pill); overflow:hidden;
  background:var(--hf-surface-3); color:var(--hf-text-secondary);
  font-family:var(--hf-font-sans); font-size:13px; font-weight:600; line-height:1;
  flex-shrink:0; user-select:none;
}
.hf-avatar img{ width:100%; height:100%; object-fit:cover; display:block; }
.hf-avatar--square{ border-radius:var(--hf-radius-md); }
.hf-avatar--ring{ box-shadow:0 0 0 2px var(--hf-bg), 0 0 0 3px var(--hf-border-strong); }
.hf-avatar--xs{ width:24px; height:24px; font-size:10px; }
.hf-avatar--sm{ width:28px; height:28px; font-size:11px; }
.hf-avatar--lg{ width:48px; height:48px; font-size:16px; }
.hf-avatar--xl{ width:64px; height:64px; font-size:20px; }
.hf-avatar__status{ position:absolute; right:-1px; bottom:-1px; width:11px; height:11px;
  border-radius:999px; border:2px solid var(--hf-bg); background:var(--hf-success); }
.hf-avatar__status--busy{ background:var(--hf-live); }
.hf-avatar__status--off{ background:var(--hf-neutral-500); }
`;
let injected = false;
function ensure() {
  if (injected || typeof document === 'undefined') return;
  const s = document.createElement('style');
  s.id = 'hf-avatar-css';
  s.textContent = CSS;
  document.head.appendChild(s);
  injected = true;
}
function initials(name = '') {
  return name.trim().split(/\s+/).slice(0, 2).map(w => w[0] || '').join('').toUpperCase();
}
function Avatar({
  src,
  name = '',
  size = 'md',
  square = false,
  ring = false,
  status,
  className = '',
  ...rest
}) {
  ensure();
  const cls = ['hf-avatar', size !== 'md' && `hf-avatar--${size}`, square && 'hf-avatar--square', ring && 'hf-avatar--ring', className].filter(Boolean).join(' ');
  return /*#__PURE__*/React.createElement("span", _extends({
    className: cls
  }, rest), src ? /*#__PURE__*/React.createElement("img", {
    src: src,
    alt: name
  }) : /*#__PURE__*/React.createElement("span", null, initials(name) || '?'), status && /*#__PURE__*/React.createElement("span", {
    className: 'hf-avatar__status hf-avatar__status--' + status
  }));
}
Object.assign(__ds_scope, { Avatar });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Avatar.jsx", error: String((e && e.message) || e) }); }

// components/core/Badge.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const CSS = `
.hf-badge{
  display:inline-flex; align-items:center; gap:5px; vertical-align:middle;
  height:20px; padding:0 8px; border-radius:var(--hf-radius-pill);
  font-family:var(--hf-font-sans); font-size:11px; font-weight:600;
  letter-spacing:0.02em; line-height:1; white-space:nowrap;
  background:var(--hf-fill-medium); color:var(--hf-text-secondary);
  border:1px solid transparent;
}
.hf-badge--neutral{ background:var(--hf-fill-medium); color:var(--hf-text-secondary); }
.hf-badge--new{ background:var(--hf-white); color:var(--hf-text-inverse); }
.hf-badge--pro{ background:var(--hf-warning-dim); color:var(--hf-warning); }
.hf-badge--accent{ background:var(--hf-accent-dim); color:var(--hf-accent); }
.hf-badge--success{ background:var(--hf-success-dim); color:var(--hf-success); }
.hf-badge--danger{ background:var(--hf-danger-dim); color:var(--hf-danger); }
.hf-badge--info{ background:var(--hf-info-dim); color:var(--hf-info); }
.hf-badge--outline{ background:transparent; border-color:var(--hf-border-strong); color:var(--hf-text-secondary); }
.hf-badge--uppercase{ text-transform:uppercase; letter-spacing:0.08em; font-weight:700; }
.hf-badge__dot{ width:6px; height:6px; border-radius:999px; background:currentColor; }
.hf-badge__dot--live{ background:var(--hf-live); box-shadow:0 0 0 0 rgba(255,77,109,.6); animation:hf-badge-pulse 1.6s var(--hf-ease-out) infinite; }
@keyframes hf-badge-pulse{ 70%{ box-shadow:0 0 0 6px rgba(255,77,109,0); } 100%{ box-shadow:0 0 0 0 rgba(255,77,109,0); } }
`;
let injected = false;
function ensure() {
  if (injected || typeof document === 'undefined') return;
  const s = document.createElement('style');
  s.id = 'hf-badge-css';
  s.textContent = CSS;
  document.head.appendChild(s);
  injected = true;
}
function Badge({
  variant = 'neutral',
  uppercase = false,
  dot = false,
  live = false,
  className = '',
  children,
  ...rest
}) {
  ensure();
  const cls = ['hf-badge', `hf-badge--${variant}`, uppercase && 'hf-badge--uppercase', className].filter(Boolean).join(' ');
  return /*#__PURE__*/React.createElement("span", _extends({
    className: cls
  }, rest), (dot || live) && /*#__PURE__*/React.createElement("span", {
    className: 'hf-badge__dot' + (live ? ' hf-badge__dot--live' : '')
  }), children);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Badge.jsx", error: String((e && e.message) || e) }); }

// components/core/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/* Higgsfield Button — injected stylesheet so hover/active/focus are real. */
const CSS = `
.hf-btn{
  --_h:40px; --_px:18px; --_fs:14px; --_gap:8px;
  display:inline-flex; align-items:center; justify-content:center; gap:var(--_gap);
  height:var(--_h); padding:0 var(--_px); font-family:var(--hf-font-sans);
  font-size:var(--_fs); font-weight:600; letter-spacing:-0.01em; line-height:1;
  border-radius:var(--hf-radius-md); border:1px solid transparent; cursor:pointer;
  white-space:nowrap; user-select:none; text-decoration:none;
  transition:background var(--hf-dur-fast) var(--hf-ease-out),
             border-color var(--hf-dur-fast) var(--hf-ease-out),
             color var(--hf-dur-fast) var(--hf-ease-out),
             transform var(--hf-dur-fast) var(--hf-ease-out),
             opacity var(--hf-dur-fast) var(--hf-ease-out);
}
.hf-btn:active{ transform:scale(var(--hf-press-scale)); }
.hf-btn:focus-visible{ outline:none; box-shadow:var(--hf-focus-ring); }
.hf-btn[disabled],.hf-btn[aria-disabled="true"]{ pointer-events:none; opacity:.42; }
.hf-btn--sm{ --_h:32px; --_px:12px; --_fs:13px; --_gap:6px; }
.hf-btn--lg{ --_h:48px; --_px:24px; --_fs:15px; }
.hf-btn--block{ width:100%; }
.hf-btn--icononly{ padding:0; width:var(--_h); }

.hf-btn--primary{ background:var(--hf-action); color:var(--hf-action-fg); box-shadow:var(--hf-sheen-top); }
.hf-btn--primary:hover{ background:var(--hf-action-hover); }
.hf-btn--primary:active{ background:var(--hf-action-active); }

.hf-btn--secondary{ background:var(--hf-fill-medium); color:var(--hf-text-primary); border-color:var(--hf-border); }
.hf-btn--secondary:hover{ background:var(--hf-fill-strong); border-color:var(--hf-border-strong); }

.hf-btn--ghost{ background:transparent; color:var(--hf-text-secondary); }
.hf-btn--ghost:hover{ background:var(--hf-fill-soft); color:var(--hf-text-primary); }

.hf-btn--outline{ background:transparent; color:var(--hf-text-primary); border-color:var(--hf-border-strong); }
.hf-btn--outline:hover{ background:var(--hf-fill-soft); border-color:var(--hf-border-focus); }

.hf-btn--accent{ background:var(--hf-accent); color:var(--hf-accent-fg); }
.hf-btn--accent:hover{ background:var(--hf-accent-hover); }

.hf-btn--danger{ background:var(--hf-danger); color:#fff; }
.hf-btn--danger:hover{ filter:brightness(1.08); }

.hf-btn__spin{ width:1em; height:1em; border-radius:999px; border:2px solid currentColor;
  border-top-color:transparent; animation:hf-btn-spin .7s linear infinite; }
@keyframes hf-btn-spin{ to{ transform:rotate(360deg); } }
.hf-btn--loading{ color:transparent !important; position:relative; }
.hf-btn--loading .hf-btn__spin{ position:absolute; color:var(--hf-action-fg); }
.hf-btn--loading.hf-btn--secondary .hf-btn__spin,
.hf-btn--loading.hf-btn--ghost .hf-btn__spin,
.hf-btn--loading.hf-btn--outline .hf-btn__spin{ color:var(--hf-text-primary); }
`;
let injected = false;
function ensure() {
  if (injected || typeof document === 'undefined') return;
  const s = document.createElement('style');
  s.id = 'hf-button-css';
  s.textContent = CSS;
  document.head.appendChild(s);
  injected = true;
}
function Button({
  variant = 'primary',
  size = 'md',
  block = false,
  loading = false,
  iconOnly = false,
  leadingIcon = null,
  trailingIcon = null,
  disabled = false,
  as = 'button',
  className = '',
  children,
  ...rest
}) {
  ensure();
  const Tag = as;
  const cls = ['hf-btn', `hf-btn--${variant}`, size !== 'md' && `hf-btn--${size}`, block && 'hf-btn--block', iconOnly && 'hf-btn--icononly', loading && 'hf-btn--loading', className].filter(Boolean).join(' ');
  return /*#__PURE__*/React.createElement(Tag, _extends({
    className: cls,
    disabled: Tag === 'button' ? disabled || loading : undefined,
    "aria-disabled": disabled || loading || undefined
  }, rest), loading && /*#__PURE__*/React.createElement("span", {
    className: "hf-btn__spin",
    "aria-hidden": "true"
  }), leadingIcon && /*#__PURE__*/React.createElement("span", {
    className: "hf-btn__icon",
    "aria-hidden": "true"
  }, leadingIcon), !iconOnly && children, iconOnly && children, trailingIcon && /*#__PURE__*/React.createElement("span", {
    className: "hf-btn__icon",
    "aria-hidden": "true"
  }, trailingIcon));
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Button.jsx", error: String((e && e.message) || e) }); }

// components/core/IconButton.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const CSS = `
.hf-iconbtn{
  --_s:40px;
  display:inline-flex; align-items:center; justify-content:center;
  width:var(--_s); height:var(--_s); padding:0; cursor:pointer;
  border-radius:var(--hf-radius-md); border:1px solid transparent;
  background:transparent; color:var(--hf-text-secondary);
  transition:background var(--hf-dur-fast) var(--hf-ease-out),
             color var(--hf-dur-fast) var(--hf-ease-out),
             border-color var(--hf-dur-fast) var(--hf-ease-out),
             transform var(--hf-dur-fast) var(--hf-ease-out);
}
.hf-iconbtn svg{ width:20px; height:20px; display:block; }
.hf-iconbtn:hover{ background:var(--hf-fill-soft); color:var(--hf-text-primary); }
.hf-iconbtn:active{ transform:scale(var(--hf-press-scale)); }
.hf-iconbtn:focus-visible{ outline:none; box-shadow:var(--hf-focus-ring); }
.hf-iconbtn[disabled]{ pointer-events:none; opacity:.4; }
.hf-iconbtn--round{ border-radius:var(--hf-radius-pill); }
.hf-iconbtn--sm{ --_s:32px; }
.hf-iconbtn--sm svg{ width:16px; height:16px; }
.hf-iconbtn--lg{ --_s:48px; }
.hf-iconbtn--lg svg{ width:24px; height:24px; }
.hf-iconbtn--solid{ background:var(--hf-fill-medium); border-color:var(--hf-border); color:var(--hf-text-primary); }
.hf-iconbtn--solid:hover{ background:var(--hf-fill-strong); border-color:var(--hf-border-strong); }
.hf-iconbtn--glass{ background:var(--hf-glass-bg); -webkit-backdrop-filter:var(--hf-blur-md); backdrop-filter:var(--hf-blur-md); border-color:var(--hf-glass-border); color:#fff; }
.hf-iconbtn--primary{ background:var(--hf-action); color:var(--hf-action-fg); }
.hf-iconbtn--primary:hover{ background:var(--hf-action-hover); }
`;
let injected = false;
function ensure() {
  if (injected || typeof document === 'undefined') return;
  const s = document.createElement('style');
  s.id = 'hf-iconbtn-css';
  s.textContent = CSS;
  document.head.appendChild(s);
  injected = true;
}
function IconButton({
  variant = 'ghost',
  size = 'md',
  round = false,
  className = '',
  children,
  ...rest
}) {
  ensure();
  const cls = ['hf-iconbtn', variant !== 'ghost' && `hf-iconbtn--${variant}`, size !== 'md' && `hf-iconbtn--${size}`, round && 'hf-iconbtn--round', className].filter(Boolean).join(' ');
  return /*#__PURE__*/React.createElement("button", _extends({
    className: cls
  }, rest), children);
}
Object.assign(__ds_scope, { IconButton });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/IconButton.jsx", error: String((e && e.message) || e) }); }

// components/core/Spinner.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const CSS = `
.hf-spinner{ display:inline-block; border-radius:999px; border:2px solid var(--hf-fill-strong);
  border-top-color:var(--hf-text-primary); width:20px; height:20px;
  animation:hf-spinner-rot .7s linear infinite; }
.hf-spinner--accent{ border-top-color:var(--hf-accent); }
@keyframes hf-spinner-rot{ to{ transform:rotate(360deg); } }
.hf-spinner--xs{ width:14px; height:14px; border-width:2px; }
.hf-spinner--lg{ width:28px; height:28px; border-width:3px; }
`;
let injected = false;
function ensure() {
  if (injected || typeof document === 'undefined') return;
  const s = document.createElement('style');
  s.id = 'hf-spinner-css';
  s.textContent = CSS;
  document.head.appendChild(s);
  injected = true;
}
function Spinner({
  size = 'md',
  accent = false,
  className = '',
  label = 'Loading',
  ...rest
}) {
  ensure();
  const cls = ['hf-spinner', size !== 'md' && `hf-spinner--${size}`, accent && 'hf-spinner--accent', className].filter(Boolean).join(' ');
  return /*#__PURE__*/React.createElement("span", _extends({
    className: cls,
    role: "status",
    "aria-label": label
  }, rest));
}
Object.assign(__ds_scope, { Spinner });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Spinner.jsx", error: String((e && e.message) || e) }); }

// components/core/Tag.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const CSS = `
.hf-tag{
  display:inline-flex; align-items:center; gap:6px;
  height:30px; padding:0 12px; border-radius:var(--hf-radius-pill);
  font-family:var(--hf-font-sans); font-size:13px; font-weight:500; line-height:1;
  background:var(--hf-fill-soft); color:var(--hf-text-secondary);
  border:1px solid var(--hf-border); cursor:default; white-space:nowrap;
  transition:background var(--hf-dur-fast) var(--hf-ease-out),
             color var(--hf-dur-fast) var(--hf-ease-out),
             border-color var(--hf-dur-fast) var(--hf-ease-out);
}
.hf-tag--clickable{ cursor:pointer; }
.hf-tag--clickable:hover{ background:var(--hf-fill-medium); color:var(--hf-text-primary); border-color:var(--hf-border-strong); }
.hf-tag--selected{ background:var(--hf-white); color:var(--hf-text-inverse); border-color:var(--hf-white); font-weight:600; }
.hf-tag--selected:hover{ background:var(--hf-action-hover); color:var(--hf-text-inverse); }
.hf-tag__icon{ display:inline-flex; }
.hf-tag__icon svg{ width:14px; height:14px; display:block; }
.hf-tag__x{ display:inline-flex; align-items:center; justify-content:center;
  width:16px; height:16px; margin-right:-4px; border-radius:999px; cursor:pointer;
  color:inherit; opacity:.6; }
.hf-tag__x:hover{ opacity:1; background:rgba(127,127,127,.25); }
.hf-tag--sm{ height:24px; padding:0 9px; font-size:12px; }
`;
let injected = false;
function ensure() {
  if (injected || typeof document === 'undefined') return;
  const s = document.createElement('style');
  s.id = 'hf-tag-css';
  s.textContent = CSS;
  document.head.appendChild(s);
  injected = true;
}
function Tag({
  selected = false,
  size = 'md',
  icon = null,
  onRemove,
  onClick,
  className = '',
  children,
  ...rest
}) {
  ensure();
  const clickable = !!onClick || selected !== undefined && !!onClick;
  const isClickable = !!onClick;
  const cls = ['hf-tag', isClickable && 'hf-tag--clickable', selected && 'hf-tag--selected', size === 'sm' && 'hf-tag--sm', className].filter(Boolean).join(' ');
  return /*#__PURE__*/React.createElement("span", _extends({
    className: cls,
    onClick: onClick,
    role: isClickable ? 'button' : undefined
  }, rest), icon && /*#__PURE__*/React.createElement("span", {
    className: "hf-tag__icon"
  }, icon), children, onRemove && /*#__PURE__*/React.createElement("span", {
    className: "hf-tag__x",
    role: "button",
    "aria-label": "Remove",
    onClick: e => {
      e.stopPropagation();
      onRemove(e);
    }
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 16 16",
    fill: "none"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M4 4l8 8M12 4l-8 8",
    stroke: "currentColor",
    "stroke-width": "1.6",
    "stroke-linecap": "round"
  }))));
}
Object.assign(__ds_scope, { Tag });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Tag.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Dialog.jsx
try { (() => {
const CSS = `
.hf-dialog__scrim{ position:fixed; inset:0; z-index:var(--hf-z-modal); background:var(--hf-scrim);
  -webkit-backdrop-filter:var(--hf-blur-sm); backdrop-filter:var(--hf-blur-sm);
  display:flex; align-items:center; justify-content:center; padding:24px;
  animation:hf-dialog-fade var(--hf-dur-base) var(--hf-ease-out); }
@keyframes hf-dialog-fade{ from{ opacity:0; } to{ opacity:1; } }
.hf-dialog{ width:100%; max-width:480px; background:var(--hf-surface-1);
  border:1px solid var(--hf-border-strong); border-radius:var(--hf-radius-2xl);
  box-shadow:var(--hf-shadow-xl), var(--hf-sheen-top); overflow:hidden;
  animation:hf-dialog-pop var(--hf-dur-base) var(--hf-ease-out); }
@keyframes hf-dialog-pop{ from{ opacity:0; transform:translateY(8px) scale(.98); } to{ opacity:1; transform:none; } }
.hf-dialog__head{ display:flex; align-items:flex-start; justify-content:space-between; gap:16px; padding:22px 22px 0; }
.hf-dialog__title{ font:700 19px var(--hf-font-sans); letter-spacing:-0.01em; color:var(--hf-text-primary); margin:0; }
.hf-dialog__desc{ font:400 14px var(--hf-font-sans); color:var(--hf-text-secondary); margin:6px 0 0; line-height:1.5; }
.hf-dialog__x{ flex-shrink:0; width:30px; height:30px; border-radius:var(--hf-radius-sm); border:none;
  background:var(--hf-fill-soft); color:var(--hf-text-secondary); cursor:pointer; display:flex; align-items:center; justify-content:center; }
.hf-dialog__x:hover{ background:var(--hf-fill-medium); color:var(--hf-text-primary); }
.hf-dialog__body{ padding:16px 22px; }
.hf-dialog__foot{ display:flex; justify-content:flex-end; gap:10px; padding:8px 22px 22px; }
`;
let injected = false;
function ensure() {
  if (injected || typeof document === 'undefined') return;
  const s = document.createElement('style');
  s.id = 'hf-dialog-css';
  s.textContent = CSS;
  document.head.appendChild(s);
  injected = true;
}
function Dialog({
  open,
  onClose,
  title,
  description,
  footer,
  className = '',
  children
}) {
  ensure();
  React.useEffect(() => {
    if (!open) return;
    const h = e => {
      if (e.key === 'Escape') onClose && onClose();
    };
    document.addEventListener('keydown', h);
    return () => document.removeEventListener('keydown', h);
  }, [open, onClose]);
  if (!open) return null;
  return /*#__PURE__*/React.createElement("div", {
    className: "hf-dialog__scrim",
    onMouseDown: e => {
      if (e.target === e.currentTarget) onClose && onClose();
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: 'hf-dialog ' + className,
    role: "dialog",
    "aria-modal": "true",
    "aria-label": title
  }, (title || onClose) && /*#__PURE__*/React.createElement("div", {
    className: "hf-dialog__head"
  }, /*#__PURE__*/React.createElement("div", null, title && /*#__PURE__*/React.createElement("h2", {
    className: "hf-dialog__title"
  }, title), description && /*#__PURE__*/React.createElement("p", {
    className: "hf-dialog__desc"
  }, description)), onClose && /*#__PURE__*/React.createElement("button", {
    className: "hf-dialog__x",
    onClick: onClose,
    "aria-label": "Close"
  }, /*#__PURE__*/React.createElement("svg", {
    width: "16",
    height: "16",
    viewBox: "0 0 16 16",
    fill: "none"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M4 4l8 8M12 4l-8 8",
    stroke: "currentColor",
    "stroke-width": "1.6",
    "stroke-linecap": "round"
  })))), children && /*#__PURE__*/React.createElement("div", {
    className: "hf-dialog__body"
  }, children), footer && /*#__PURE__*/React.createElement("div", {
    className: "hf-dialog__foot"
  }, footer)));
}
Object.assign(__ds_scope, { Dialog });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Dialog.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Toast.jsx
try { (() => {
const CSS = `
.hf-toast{ display:flex; align-items:flex-start; gap:11px; width:340px; max-width:88vw;
  padding:13px 14px; background:var(--hf-glass-bg); -webkit-backdrop-filter:var(--hf-blur-md);
  backdrop-filter:var(--hf-blur-md); border:1px solid var(--hf-border-strong);
  border-radius:var(--hf-radius-md); box-shadow:var(--hf-shadow-lg), var(--hf-sheen-top);
  animation:hf-toast-in var(--hf-dur-slow) var(--hf-ease-spring); }
@keyframes hf-toast-in{ from{ opacity:0; transform:translateY(10px) scale(.97); } to{ opacity:1; transform:none; } }
.hf-toast__icon{ flex-shrink:0; width:18px; height:18px; margin-top:1px; }
.hf-toast--success .hf-toast__icon{ color:var(--hf-success); }
.hf-toast--danger .hf-toast__icon{ color:var(--hf-danger); }
.hf-toast--info .hf-toast__icon{ color:var(--hf-info); }
.hf-toast--neutral .hf-toast__icon{ color:var(--hf-text-secondary); }
.hf-toast__body{ flex:1; min-width:0; }
.hf-toast__title{ font:600 14px var(--hf-font-sans); color:var(--hf-text-primary); }
.hf-toast__msg{ font:400 13px var(--hf-font-sans); color:var(--hf-text-secondary); margin-top:2px; line-height:1.4; }
.hf-toast__x{ flex-shrink:0; width:22px; height:22px; border:none; background:none; cursor:pointer;
  color:var(--hf-text-tertiary); border-radius:var(--hf-radius-xs); display:flex; align-items:center; justify-content:center; }
.hf-toast__x:hover{ color:var(--hf-text-primary); background:var(--hf-fill-soft); }
.hf-toast__stack{ position:fixed; z-index:var(--hf-z-toast); bottom:20px; right:20px;
  display:flex; flex-direction:column; gap:10px; align-items:flex-end; }
`;
let injected = false;
function ensure() {
  if (injected || typeof document === 'undefined') return;
  const s = document.createElement('style');
  s.id = 'hf-toast-css';
  s.textContent = CSS;
  document.head.appendChild(s);
  injected = true;
}
const ICONS = {
  success: /*#__PURE__*/React.createElement("path", {
    d: "M4 9l3.5 3.5L15 5",
    stroke: "currentColor",
    strokeWidth: "1.8",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }),
  danger: /*#__PURE__*/React.createElement("path", {
    d: "M9 5v5M9 13h.01",
    stroke: "currentColor",
    strokeWidth: "1.8",
    strokeLinecap: "round"
  }),
  info: /*#__PURE__*/React.createElement("path", {
    d: "M9 8v5M9 5h.01",
    stroke: "currentColor",
    strokeWidth: "1.8",
    strokeLinecap: "round"
  }),
  neutral: /*#__PURE__*/React.createElement("circle", {
    cx: "9",
    cy: "9",
    r: "2",
    fill: "currentColor"
  })
};
function Toast({
  variant = 'neutral',
  title,
  message,
  onClose,
  className = ''
}) {
  ensure();
  return /*#__PURE__*/React.createElement("div", {
    className: 'hf-toast hf-toast--' + variant + (className ? ' ' + className : ''),
    role: "status"
  }, /*#__PURE__*/React.createElement("svg", {
    className: "hf-toast__icon",
    viewBox: "0 0 18 18",
    fill: "none"
  }, ICONS[variant]), /*#__PURE__*/React.createElement("div", {
    className: "hf-toast__body"
  }, title && /*#__PURE__*/React.createElement("div", {
    className: "hf-toast__title"
  }, title), message && /*#__PURE__*/React.createElement("div", {
    className: "hf-toast__msg"
  }, message)), onClose && /*#__PURE__*/React.createElement("button", {
    className: "hf-toast__x",
    onClick: onClose,
    "aria-label": "Dismiss"
  }, /*#__PURE__*/React.createElement("svg", {
    width: "14",
    height: "14",
    viewBox: "0 0 14 14",
    fill: "none"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M3.5 3.5l7 7M10.5 3.5l-7 7",
    stroke: "currentColor",
    strokeWidth: "1.5",
    strokeLinecap: "round"
  }))));
}
function ToastStack({
  children
}) {
  ensure();
  return /*#__PURE__*/React.createElement("div", {
    className: "hf-toast__stack"
  }, children);
}
Object.assign(__ds_scope, { Toast, ToastStack });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Toast.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Tooltip.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const CSS = `
.hf-tip{ position:relative; display:inline-flex; }
.hf-tip__bubble{ position:absolute; z-index:var(--hf-z-tooltip); pointer-events:none;
  background:var(--hf-neutral-100); color:var(--hf-neutral-950);
  font:600 12px var(--hf-font-sans); line-height:1.3; letter-spacing:-0.005em;
  padding:6px 9px; border-radius:var(--hf-radius-sm); white-space:nowrap;
  box-shadow:var(--hf-shadow-md); opacity:0; transform:translateY(2px) scale(.96);
  transition:opacity var(--hf-dur-fast) var(--hf-ease-out), transform var(--hf-dur-fast) var(--hf-ease-out); }
.hf-tip:hover .hf-tip__bubble, .hf-tip:focus-within .hf-tip__bubble{ opacity:1; transform:translateY(0) scale(1); }
.hf-tip__bubble--top{ bottom:calc(100% + 8px); left:50%; transform-origin:bottom center; margin-left:-50%; left:50%; }
.hf-tip--top .hf-tip__bubble{ bottom:calc(100% + 8px); left:50%; translate:-50% 0; }
.hf-tip--bottom .hf-tip__bubble{ top:calc(100% + 8px); left:50%; translate:-50% 0; }
.hf-tip--left .hf-tip__bubble{ right:calc(100% + 8px); top:50%; translate:0 -50%; }
.hf-tip--right .hf-tip__bubble{ left:calc(100% + 8px); top:50%; translate:0 -50%; }
.hf-tip__kbd{ font-family:var(--hf-font-mono); opacity:.6; margin-left:6px; }
`;
let injected = false;
function ensure() {
  if (injected || typeof document === 'undefined') return;
  const s = document.createElement('style');
  s.id = 'hf-tip-css';
  s.textContent = CSS;
  document.head.appendChild(s);
  injected = true;
}
function Tooltip({
  label,
  kbd,
  side = 'top',
  className = '',
  children,
  ...rest
}) {
  ensure();
  return /*#__PURE__*/React.createElement("span", _extends({
    className: 'hf-tip hf-tip--' + side + (className ? ' ' + className : '')
  }, rest), children, /*#__PURE__*/React.createElement("span", {
    className: "hf-tip__bubble",
    role: "tooltip"
  }, label, kbd && /*#__PURE__*/React.createElement("span", {
    className: "hf-tip__kbd"
  }, kbd)));
}
Object.assign(__ds_scope, { Tooltip });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Tooltip.jsx", error: String((e && e.message) || e) }); }

// components/forms/Input.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const CSS = `
.hf-field{ display:flex; flex-direction:column; gap:7px; }
.hf-field__label{ font:600 13px var(--hf-font-sans); color:var(--hf-text-secondary); }
.hf-field__hint{ font:400 12px var(--hf-font-sans); color:var(--hf-text-tertiary); }
.hf-field__hint--error{ color:var(--hf-danger); }
.hf-input{
  display:flex; align-items:center; gap:8px; height:40px; padding:0 12px;
  background:var(--hf-surface-2); border:1px solid var(--hf-border);
  border-radius:var(--hf-radius-md); transition:border-color var(--hf-dur-fast) var(--hf-ease-out),
  box-shadow var(--hf-dur-fast) var(--hf-ease-out), background var(--hf-dur-fast) var(--hf-ease-out); }
.hf-input:hover{ border-color:var(--hf-border-strong); }
.hf-input--focus{ border-color:var(--hf-border-focus); box-shadow:0 0 0 3px rgba(255,255,255,.08); background:var(--hf-surface-2); }
.hf-input--error{ border-color:var(--hf-danger); }
.hf-input--error.hf-input--focus{ box-shadow:0 0 0 3px var(--hf-danger-dim); }
.hf-input--lg{ height:48px; }
.hf-input--sm{ height:32px; }
.hf-input input{
  flex:1; min-width:0; background:none; border:none; outline:none; color:var(--hf-text-primary);
  font:400 15px var(--hf-font-sans); padding:0; }
.hf-input input::placeholder{ color:var(--hf-text-tertiary); }
.hf-input__affix{ display:inline-flex; color:var(--hf-text-tertiary); flex-shrink:0; }
.hf-input__affix svg{ width:18px; height:18px; display:block; }
.hf-input--disabled{ opacity:.5; pointer-events:none; }
`;
let injected = false;
function ensure() {
  if (injected || typeof document === 'undefined') return;
  const s = document.createElement('style');
  s.id = 'hf-input-css';
  s.textContent = CSS;
  document.head.appendChild(s);
  injected = true;
}
function Input({
  label,
  hint,
  error,
  size = 'md',
  leadingIcon,
  trailingIcon,
  disabled = false,
  className = '',
  id,
  ...rest
}) {
  ensure();
  const [focus, setFocus] = React.useState(false);
  const fid = id || React.useId();
  const boxCls = ['hf-input', size !== 'md' && `hf-input--${size}`, focus && 'hf-input--focus', error && 'hf-input--error', disabled && 'hf-input--disabled'].filter(Boolean).join(' ');
  return /*#__PURE__*/React.createElement("div", {
    className: 'hf-field ' + className
  }, label && /*#__PURE__*/React.createElement("label", {
    className: "hf-field__label",
    htmlFor: fid
  }, label), /*#__PURE__*/React.createElement("div", {
    className: boxCls
  }, leadingIcon && /*#__PURE__*/React.createElement("span", {
    className: "hf-input__affix"
  }, leadingIcon), /*#__PURE__*/React.createElement("input", _extends({
    id: fid,
    disabled: disabled,
    onFocus: e => {
      setFocus(true);
      rest.onFocus && rest.onFocus(e);
    },
    onBlur: e => {
      setFocus(false);
      rest.onBlur && rest.onBlur(e);
    }
  }, rest)), trailingIcon && /*#__PURE__*/React.createElement("span", {
    className: "hf-input__affix"
  }, trailingIcon)), (hint || error) && /*#__PURE__*/React.createElement("span", {
    className: 'hf-field__hint' + (error ? ' hf-field__hint--error' : '')
  }, error || hint));
}
Object.assign(__ds_scope, { Input });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Input.jsx", error: String((e && e.message) || e) }); }

// components/forms/SegmentedControl.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const CSS = `
.hf-seg{ display:inline-flex; align-items:center; gap:2px; padding:3px;
  background:var(--hf-surface-2); border:1px solid var(--hf-border);
  border-radius:var(--hf-radius-pill); position:relative; }
.hf-seg__opt{ position:relative; z-index:1; display:inline-flex; align-items:center; gap:6px;
  height:30px; padding:0 14px; border-radius:999px; cursor:pointer; border:none; background:none;
  font:600 13px var(--hf-font-sans); color:var(--hf-text-secondary); white-space:nowrap;
  transition:color var(--hf-dur-fast) var(--hf-ease-out); }
.hf-seg__opt svg{ width:16px; height:16px; }
.hf-seg__opt:hover{ color:var(--hf-text-primary); }
.hf-seg__opt--active{ color:var(--hf-text-inverse); }
.hf-seg__opt:focus-visible{ outline:none; box-shadow:var(--hf-focus-ring); border-radius:999px; }
.hf-seg__pill{ position:absolute; z-index:0; top:3px; bottom:3px; border-radius:999px;
  background:var(--hf-white); box-shadow:var(--hf-shadow-sm);
  transition:left var(--hf-dur-base) var(--hf-ease-out), width var(--hf-dur-base) var(--hf-ease-out); }
.hf-seg--sm .hf-seg__opt{ height:26px; padding:0 11px; font-size:12px; }
`;
let injected = false;
function ensure() {
  if (injected || typeof document === 'undefined') return;
  const s = document.createElement('style');
  s.id = 'hf-seg-css';
  s.textContent = CSS;
  document.head.appendChild(s);
  injected = true;
}
function SegmentedControl({
  options = [],
  value,
  defaultValue,
  onChange,
  size = 'md',
  className = '',
  ...rest
}) {
  ensure();
  const norm = options.map(o => typeof o === 'string' ? {
    value: o,
    label: o
  } : o);
  const isControlled = value !== undefined;
  const [internal, setInternal] = React.useState(defaultValue ?? norm[0]?.value);
  const active = isControlled ? value : internal;
  const wrapRef = React.useRef(null);
  const [pill, setPill] = React.useState({
    left: 3,
    width: 0
  });
  React.useLayoutEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    const el = wrap.querySelector('[data-active="true"]');
    if (el) setPill({
      left: el.offsetLeft,
      width: el.offsetWidth
    });
  }, [active, options]);
  const pick = v => {
    if (!isControlled) setInternal(v);
    onChange && onChange(v);
  };
  const cls = ['hf-seg', size === 'sm' && 'hf-seg--sm', className].filter(Boolean).join(' ');
  return /*#__PURE__*/React.createElement("div", _extends({
    className: cls,
    ref: wrapRef,
    role: "tablist"
  }, rest), /*#__PURE__*/React.createElement("span", {
    className: "hf-seg__pill",
    style: {
      left: pill.left,
      width: pill.width
    }
  }), norm.map(o => /*#__PURE__*/React.createElement("button", {
    key: o.value,
    type: "button",
    role: "tab",
    "aria-selected": active === o.value,
    "data-active": active === o.value,
    className: 'hf-seg__opt' + (active === o.value ? ' hf-seg__opt--active' : ''),
    onClick: () => pick(o.value)
  }, o.icon, o.label)));
}
Object.assign(__ds_scope, { SegmentedControl });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/SegmentedControl.jsx", error: String((e && e.message) || e) }); }

// components/forms/Select.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const CSS = `
.hf-select{ position:relative; display:inline-block; }
.hf-select__trigger{ display:inline-flex; align-items:center; gap:8px; justify-content:space-between;
  min-width:160px; height:40px; padding:0 12px; width:100%;
  background:var(--hf-surface-2); border:1px solid var(--hf-border); border-radius:var(--hf-radius-md);
  color:var(--hf-text-primary); font:500 14px var(--hf-font-sans); cursor:pointer;
  transition:border-color var(--hf-dur-fast) var(--hf-ease-out); }
.hf-select__trigger:hover{ border-color:var(--hf-border-strong); }
.hf-select__trigger:focus-visible{ outline:none; box-shadow:var(--hf-focus-ring); }
.hf-select--open .hf-select__trigger{ border-color:var(--hf-border-focus); }
.hf-select__val{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.hf-select__val--ph{ color:var(--hf-text-tertiary); }
.hf-select__chev{ width:16px; height:16px; color:var(--hf-text-tertiary); flex-shrink:0;
  transition:transform var(--hf-dur-fast) var(--hf-ease-out); }
.hf-select--open .hf-select__chev{ transform:rotate(180deg); }
.hf-select__menu{ position:absolute; z-index:var(--hf-z-overlay); top:calc(100% + 6px); left:0; right:0;
  min-width:100%; max-height:280px; overflow:auto; padding:6px;
  background:var(--hf-surface-2); border:1px solid var(--hf-border-strong);
  border-radius:var(--hf-radius-md); box-shadow:var(--hf-shadow-lg); }
.hf-select__opt{ display:flex; align-items:center; gap:8px; justify-content:space-between;
  padding:9px 10px; border-radius:var(--hf-radius-sm); cursor:pointer;
  font:500 14px var(--hf-font-sans); color:var(--hf-text-secondary); }
.hf-select__opt:hover{ background:var(--hf-fill-soft); color:var(--hf-text-primary); }
.hf-select__opt--active{ color:var(--hf-text-primary); }
.hf-select__opt--active::after{ content:""; width:6px; height:10px; border:solid var(--hf-accent);
  border-width:0 2px 2px 0; transform:rotate(45deg); margin-right:3px; }
`;
let injected = false;
function ensure() {
  if (injected || typeof document === 'undefined') return;
  const s = document.createElement('style');
  s.id = 'hf-select-css';
  s.textContent = CSS;
  document.head.appendChild(s);
  injected = true;
}
function Select({
  options = [],
  value,
  defaultValue,
  onChange,
  placeholder = 'Select…',
  className = '',
  style,
  ...rest
}) {
  ensure();
  const norm = options.map(o => typeof o === 'string' ? {
    value: o,
    label: o
  } : o);
  const isControlled = value !== undefined;
  const [internal, setInternal] = React.useState(defaultValue);
  const current = isControlled ? value : internal;
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef(null);
  const sel = norm.find(o => o.value === current);
  React.useEffect(() => {
    if (!open) return;
    const h = e => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, [open]);
  const pick = v => {
    if (!isControlled) setInternal(v);
    onChange && onChange(v);
    setOpen(false);
  };
  return /*#__PURE__*/React.createElement("div", {
    className: 'hf-select' + (open ? ' hf-select--open' : '') + (className ? ' ' + className : ''),
    ref: ref,
    style: style
  }, /*#__PURE__*/React.createElement("button", _extends({
    type: "button",
    className: "hf-select__trigger",
    "aria-haspopup": "listbox",
    "aria-expanded": open,
    onClick: () => setOpen(o => !o)
  }, rest), /*#__PURE__*/React.createElement("span", {
    className: 'hf-select__val' + (sel ? '' : ' hf-select__val--ph')
  }, sel ? sel.label : placeholder), /*#__PURE__*/React.createElement("svg", {
    className: "hf-select__chev",
    viewBox: "0 0 16 16",
    fill: "none"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M4 6l4 4 4-4",
    stroke: "currentColor",
    "stroke-width": "1.6",
    "stroke-linecap": "round",
    "stroke-linejoin": "round"
  }))), open && /*#__PURE__*/React.createElement("div", {
    className: "hf-select__menu",
    role: "listbox"
  }, norm.map(o => /*#__PURE__*/React.createElement("div", {
    key: o.value,
    role: "option",
    "aria-selected": current === o.value,
    className: 'hf-select__opt' + (current === o.value ? ' hf-select__opt--active' : ''),
    onClick: () => pick(o.value)
  }, /*#__PURE__*/React.createElement("span", null, o.label)))));
}
Object.assign(__ds_scope, { Select });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Select.jsx", error: String((e && e.message) || e) }); }

// components/forms/Slider.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const CSS = `
.hf-slider{ display:flex; flex-direction:column; gap:10px; }
.hf-slider__top{ display:flex; align-items:center; justify-content:space-between; }
.hf-slider__label{ font:600 13px var(--hf-font-sans); color:var(--hf-text-secondary); }
.hf-slider__value{ font:500 13px var(--hf-font-mono); color:var(--hf-text-primary);
  background:var(--hf-fill-soft); padding:2px 8px; border-radius:var(--hf-radius-sm); }
.hf-slider__track{ position:relative; height:6px; border-radius:999px; background:var(--hf-fill-strong); cursor:pointer; }
.hf-slider__fill{ position:absolute; left:0; top:0; bottom:0; border-radius:999px; background:var(--hf-white); }
.hf-slider__thumb{ position:absolute; top:50%; width:16px; height:16px; border-radius:999px;
  background:#fff; transform:translate(-50%,-50%); box-shadow:0 1px 3px rgba(0,0,0,.5);
  transition:box-shadow var(--hf-dur-fast) var(--hf-ease-out); }
.hf-slider__input{ position:absolute; inset:-7px 0; width:100%; height:20px; margin:0; opacity:0; cursor:pointer; }
.hf-slider__input:focus-visible + .hf-slider__thumb{ box-shadow:var(--hf-focus-ring); }
.hf-slider--accent .hf-slider__fill{ background:var(--hf-accent); }
`;
let injected = false;
function ensure() {
  if (injected || typeof document === 'undefined') return;
  const s = document.createElement('style');
  s.id = 'hf-slider-css';
  s.textContent = CSS;
  document.head.appendChild(s);
  injected = true;
}
function Slider({
  label,
  min = 0,
  max = 100,
  step = 1,
  value,
  defaultValue = 50,
  onChange,
  suffix = '',
  tone = 'white',
  showValue = true,
  className = '',
  ...rest
}) {
  ensure();
  const isControlled = value !== undefined;
  const [internal, setInternal] = React.useState(defaultValue);
  const v = isControlled ? value : internal;
  const pct = (v - min) / (max - min) * 100;
  const set = nv => {
    if (!isControlled) setInternal(nv);
    onChange && onChange(nv);
  };
  const cls = ['hf-slider', tone === 'accent' && 'hf-slider--accent', className].filter(Boolean).join(' ');
  return /*#__PURE__*/React.createElement("div", {
    className: cls
  }, (label || showValue) && /*#__PURE__*/React.createElement("div", {
    className: "hf-slider__top"
  }, label && /*#__PURE__*/React.createElement("span", {
    className: "hf-slider__label"
  }, label), showValue && /*#__PURE__*/React.createElement("span", {
    className: "hf-slider__value"
  }, v, suffix)), /*#__PURE__*/React.createElement("div", {
    className: "hf-slider__track"
  }, /*#__PURE__*/React.createElement("div", {
    className: "hf-slider__fill",
    style: {
      width: pct + '%'
    }
  }), /*#__PURE__*/React.createElement("div", {
    className: "hf-slider__thumb",
    style: {
      left: pct + '%'
    }
  }), /*#__PURE__*/React.createElement("input", _extends({
    className: "hf-slider__input",
    type: "range",
    min: min,
    max: max,
    step: step,
    value: v,
    onChange: e => set(Number(e.target.value))
  }, rest))));
}
Object.assign(__ds_scope, { Slider });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Slider.jsx", error: String((e && e.message) || e) }); }

// components/forms/Switch.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const CSS = `
.hf-switch{ display:inline-flex; align-items:center; gap:10px; cursor:pointer; user-select:none; }
.hf-switch__track{ position:relative; width:40px; height:24px; border-radius:999px;
  background:var(--hf-fill-strong); transition:background var(--hf-dur-base) var(--hf-ease-out); flex-shrink:0; }
.hf-switch__thumb{ position:absolute; top:3px; left:3px; width:18px; height:18px; border-radius:999px;
  background:#fff; box-shadow:0 1px 2px rgba(0,0,0,.4);
  transition:transform var(--hf-dur-base) var(--hf-ease-spring); }
.hf-switch--on .hf-switch__track{ background:var(--hf-accent); }
.hf-switch--on .hf-switch__thumb{ transform:translateX(16px); }
.hf-switch--white.hf-switch--on .hf-switch__track{ background:var(--hf-white); }
.hf-switch--white.hf-switch--on .hf-switch__thumb{ background:var(--hf-text-inverse); }
.hf-switch input{ position:absolute; opacity:0; width:0; height:0; }
.hf-switch:focus-within .hf-switch__track{ box-shadow:var(--hf-focus-ring); }
.hf-switch--disabled{ opacity:.45; pointer-events:none; }
.hf-switch__label{ font:500 14px var(--hf-font-sans); color:var(--hf-text-primary); }
.hf-switch--sm .hf-switch__track{ width:32px; height:19px; }
.hf-switch--sm .hf-switch__thumb{ width:14px; height:14px; }
.hf-switch--sm.hf-switch--on .hf-switch__thumb{ transform:translateX(13px); }
`;
let injected = false;
function ensure() {
  if (injected || typeof document === 'undefined') return;
  const s = document.createElement('style');
  s.id = 'hf-switch-css';
  s.textContent = CSS;
  document.head.appendChild(s);
  injected = true;
}
function Switch({
  checked,
  defaultChecked = false,
  onChange,
  label,
  size = 'md',
  tone = 'accent',
  disabled = false,
  className = '',
  ...rest
}) {
  ensure();
  const isControlled = checked !== undefined;
  const [internal, setInternal] = React.useState(defaultChecked);
  const on = isControlled ? checked : internal;
  const toggle = () => {
    if (disabled) return;
    if (!isControlled) setInternal(!on);
    onChange && onChange(!on);
  };
  const cls = ['hf-switch', on && 'hf-switch--on', tone === 'white' && 'hf-switch--white', size === 'sm' && 'hf-switch--sm', disabled && 'hf-switch--disabled', className].filter(Boolean).join(' ');
  return /*#__PURE__*/React.createElement("label", {
    className: cls
  }, /*#__PURE__*/React.createElement("span", {
    className: "hf-switch__track",
    onClick: toggle
  }, /*#__PURE__*/React.createElement("span", {
    className: "hf-switch__thumb"
  })), /*#__PURE__*/React.createElement("input", _extends({
    type: "checkbox",
    role: "switch",
    checked: on,
    disabled: disabled,
    onChange: toggle
  }, rest)), label && /*#__PURE__*/React.createElement("span", {
    className: "hf-switch__label",
    onClick: toggle
  }, label));
}
Object.assign(__ds_scope, { Switch });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Switch.jsx", error: String((e && e.message) || e) }); }

// components/media/Card.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const CSS = `
.hf-card{ background:var(--hf-surface-1); border:1px solid var(--hf-border);
  border-radius:var(--hf-radius-lg); box-shadow:var(--hf-sheen-top); overflow:hidden; }
.hf-card--pad{ padding:18px; }
.hf-card--hover{ transition:border-color var(--hf-dur-base) var(--hf-ease-out),
  transform var(--hf-dur-base) var(--hf-ease-out), box-shadow var(--hf-dur-base) var(--hf-ease-out); cursor:pointer; }
.hf-card--hover:hover{ border-color:var(--hf-border-strong); transform:translateY(var(--hf-hover-lift));
  box-shadow:var(--hf-shadow-md), var(--hf-sheen-top); }
.hf-card--inset{ background:var(--hf-surface-inset); }
.hf-card--glass{ background:var(--hf-glass-bg); -webkit-backdrop-filter:var(--hf-blur-md);
  backdrop-filter:var(--hf-blur-md); border-color:var(--hf-glass-border); }
.hf-card__head{ display:flex; align-items:center; justify-content:space-between; gap:12px;
  padding:16px 18px; border-bottom:1px solid var(--hf-border-subtle); }
.hf-card__title{ font:600 15px var(--hf-font-sans); color:var(--hf-text-primary); margin:0; }
.hf-card__body{ padding:18px; }
`;
let injected = false;
function ensure() {
  if (injected || typeof document === 'undefined') return;
  const s = document.createElement('style');
  s.id = 'hf-card-css';
  s.textContent = CSS;
  document.head.appendChild(s);
  injected = true;
}
function Card({
  variant = 'default',
  padded = false,
  hover = false,
  title,
  action,
  className = '',
  children,
  ...rest
}) {
  ensure();
  const cls = ['hf-card', variant !== 'default' && `hf-card--${variant}`, padded && !title && 'hf-card--pad', hover && 'hf-card--hover', className].filter(Boolean).join(' ');
  return /*#__PURE__*/React.createElement("div", _extends({
    className: cls
  }, rest), title && /*#__PURE__*/React.createElement("div", {
    className: "hf-card__head"
  }, /*#__PURE__*/React.createElement("h3", {
    className: "hf-card__title"
  }, title), action), title ? /*#__PURE__*/React.createElement("div", {
    className: "hf-card__body"
  }, children) : children);
}
Object.assign(__ds_scope, { Card });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/media/Card.jsx", error: String((e && e.message) || e) }); }

// components/media/MediaCard.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const CSS = `
.hf-media{ position:relative; display:block; width:100%; border-radius:var(--hf-radius-xl);
  overflow:hidden; background:var(--hf-surface-2); cursor:pointer; border:1px solid var(--hf-border-subtle);
  isolation:isolate; }
.hf-media__ratio{ position:relative; width:100%; }
.hf-media__img{ position:absolute; inset:0; width:100%; height:100%; object-fit:cover; display:block;
  transition:transform var(--hf-dur-slow) var(--hf-ease-out), filter var(--hf-dur-base) var(--hf-ease-out); }
.hf-media:hover .hf-media__img{ transform:scale(1.045); }
.hf-media__scrim{ position:absolute; inset:0; background:var(--hf-grad-scrim);
  opacity:.9; transition:opacity var(--hf-dur-base) var(--hf-ease-out); }
.hf-media:hover .hf-media__scrim{ opacity:1; }
.hf-media__top{ position:absolute; top:10px; left:10px; right:10px; display:flex; align-items:center; justify-content:space-between; gap:8px; }
.hf-media__pill{ display:inline-flex; align-items:center; gap:6px; height:26px; padding:0 10px;
  background:var(--hf-glass-bg); -webkit-backdrop-filter:var(--hf-blur-md); backdrop-filter:var(--hf-blur-md);
  border:1px solid var(--hf-glass-border); border-radius:var(--hf-radius-pill);
  font:600 11px var(--hf-font-sans); color:#fff; white-space:nowrap; }
.hf-media__pill svg{ width:12px; height:12px; }
.hf-media__bottom{ position:absolute; left:14px; right:14px; bottom:13px; display:flex; align-items:flex-end; justify-content:space-between; gap:10px; }
.hf-media__label{ font-weight:700; letter-spacing:0.04em; text-transform:uppercase; color:#fff;
  font-size:15px; line-height:1.15; text-shadow:0 1px 12px rgba(0,0,0,.5); }
.hf-media__author{ display:block; margin-top:4px; font:500 11px var(--hf-font-sans); color:rgba(255,255,255,.62); text-transform:none; letter-spacing:0; }
.hf-media__play{ flex-shrink:0; width:38px; height:38px; border-radius:999px; background:rgba(255,255,255,.92);
  color:#0b0c0e; display:flex; align-items:center; justify-content:center;
  opacity:0; transform:scale(.85); transition:opacity var(--hf-dur-base) var(--hf-ease-out), transform var(--hf-dur-base) var(--hf-ease-spring); }
.hf-media:hover .hf-media__play{ opacity:1; transform:scale(1); }
.hf-media__dur{ position:absolute; right:10px; bottom:10px; }
.hf-media:focus-visible{ outline:none; box-shadow:var(--hf-glow-white); }
`;
let injected = false;
function ensure() {
  if (injected || typeof document === 'undefined') return;
  const s = document.createElement('style');
  s.id = 'hf-media-css';
  s.textContent = CSS;
  document.head.appendChild(s);
  injected = true;
}
const RATIOS = {
  '16:9': 56.25,
  '1:1': 100,
  '9:16': 177.7,
  '4:5': 125,
  '3:2': 66.6
};
function MediaCard({
  src,
  label,
  model,
  author,
  ratio = '16:9',
  badge,
  showPlay = false,
  className = '',
  onClick,
  ...rest
}) {
  ensure();
  const pad = RATIOS[ratio] || 56.25;
  return /*#__PURE__*/React.createElement("div", _extends({
    className: 'hf-media ' + className,
    role: "button",
    tabIndex: 0,
    onClick: onClick
  }, rest), /*#__PURE__*/React.createElement("div", {
    className: "hf-media__ratio",
    style: {
      paddingBottom: pad + '%'
    }
  }, src ? /*#__PURE__*/React.createElement("img", {
    className: "hf-media__img",
    src: src,
    alt: label || '',
    loading: "lazy"
  }) : /*#__PURE__*/React.createElement("div", {
    className: "hf-media__img",
    style: {
      background: 'radial-gradient(120% 120% at 70% 0%, #2a323d, #14181d 55%, #0c0e11)'
    }
  }), /*#__PURE__*/React.createElement("div", {
    className: "hf-media__scrim"
  }), /*#__PURE__*/React.createElement("div", {
    className: "hf-media__top"
  }, model && /*#__PURE__*/React.createElement("span", {
    className: "hf-media__pill"
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 12 12",
    fill: "currentColor"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M6 0l1.4 4.6L12 6 7.4 7.4 6 12 4.6 7.4 0 6l4.6-1.4z"
  })), model), badge && /*#__PURE__*/React.createElement("span", {
    className: "hf-media__pill",
    style: {
      padding: '0 9px'
    }
  }, badge)), /*#__PURE__*/React.createElement("div", {
    className: "hf-media__bottom"
  }, label && /*#__PURE__*/React.createElement("span", {
    className: "hf-media__label"
  }, label, author && /*#__PURE__*/React.createElement("span", {
    className: "hf-media__author"
  }, "by ", author)), showPlay && /*#__PURE__*/React.createElement("span", {
    className: "hf-media__play"
  }, /*#__PURE__*/React.createElement("svg", {
    width: "15",
    height: "15",
    viewBox: "0 0 15 15",
    fill: "currentColor"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M4 2.5v10l8-5z"
  }))))));
}
Object.assign(__ds_scope, { MediaCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/media/MediaCard.jsx", error: String((e && e.message) || e) }); }

// components/media/ModelPill.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const CSS = `
.hf-modelpill{ display:inline-flex; align-items:center; gap:8px; height:34px; padding:0 6px 0 11px;
  background:var(--hf-surface-2); border:1px solid var(--hf-border); border-radius:var(--hf-radius-pill);
  font:600 13px var(--hf-font-sans); color:var(--hf-text-primary); cursor:pointer; white-space:nowrap;
  transition:border-color var(--hf-dur-fast) var(--hf-ease-out), background var(--hf-dur-fast) var(--hf-ease-out); }
.hf-modelpill:hover{ border-color:var(--hf-border-strong); background:var(--hf-surface-3); }
.hf-modelpill__mark{ display:inline-flex; align-items:center; justify-content:center; width:18px; height:18px;
  border-radius:999px; background:var(--hf-white); color:var(--hf-text-inverse); flex-shrink:0; }
.hf-modelpill__mark svg{ width:11px; height:11px; }
.hf-modelpill__chev{ width:14px; height:14px; color:var(--hf-text-tertiary); margin-left:1px; }
.hf-modelpill__new{ height:16px; padding:0 6px; border-radius:999px; background:var(--hf-white);
  color:var(--hf-text-inverse); font:700 9px var(--hf-font-sans); letter-spacing:.06em; text-transform:uppercase;
  display:inline-flex; align-items:center; }
.hf-modelpill--active{ border-color:var(--hf-border-focus); }
`;
let injected = false;
function ensure() {
  if (injected || typeof document === 'undefined') return;
  const s = document.createElement('style');
  s.id = 'hf-modelpill-css';
  s.textContent = CSS;
  document.head.appendChild(s);
  injected = true;
}
function ModelPill({
  name,
  isNew = false,
  active = false,
  chevron = true,
  className = '',
  ...rest
}) {
  ensure();
  return /*#__PURE__*/React.createElement("button", _extends({
    className: 'hf-modelpill' + (active ? ' hf-modelpill--active' : '') + (className ? ' ' + className : '')
  }, rest), /*#__PURE__*/React.createElement("span", {
    className: "hf-modelpill__mark"
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 12 12",
    fill: "currentColor"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M6 0l1.4 4.6L12 6 7.4 7.4 6 12 4.6 7.4 0 6l4.6-1.4z"
  }))), /*#__PURE__*/React.createElement("span", null, name), isNew && /*#__PURE__*/React.createElement("span", {
    className: "hf-modelpill__new"
  }, "New"), chevron && /*#__PURE__*/React.createElement("svg", {
    className: "hf-modelpill__chev",
    viewBox: "0 0 14 14",
    fill: "none"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M3.5 5.5L7 9l3.5-3.5",
    stroke: "currentColor",
    strokeWidth: "1.6",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  })));
}
Object.assign(__ds_scope, { ModelPill });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/media/ModelPill.jsx", error: String((e && e.message) || e) }); }

// components/media/PromptComposer.jsx
try { (() => {
const CSS = `
.hf-composer{ background:var(--hf-surface-1); border:1px solid var(--hf-border);
  border-radius:var(--hf-radius-2xl); box-shadow:var(--hf-shadow-md), var(--hf-sheen-top);
  padding:14px 14px 12px; transition:border-color var(--hf-dur-base) var(--hf-ease-out); }
.hf-composer--focus{ border-color:var(--hf-border-strong); }
.hf-composer__refs{ display:flex; gap:8px; margin-bottom:11px; flex-wrap:wrap; }
.hf-composer__ref{ position:relative; width:48px; height:48px; border-radius:var(--hf-radius-sm);
  overflow:hidden; border:1px solid var(--hf-border); background:var(--hf-surface-3); flex-shrink:0; }
.hf-composer__ref img{ width:100%; height:100%; object-fit:cover; }
.hf-composer__ref-x{ position:absolute; top:2px; right:2px; width:16px; height:16px; border:none; border-radius:999px;
  background:rgba(0,0,0,.6); color:#fff; cursor:pointer; display:flex; align-items:center; justify-content:center; }
.hf-composer__input{ width:100%; resize:none; border:none; outline:none; background:none;
  color:var(--hf-text-primary); font:400 16px var(--hf-font-sans); line-height:1.45;
  min-height:52px; padding:4px 4px 0; }
.hf-composer__input::placeholder{ color:var(--hf-text-tertiary); }
.hf-composer__bar{ display:flex; align-items:center; gap:8px; margin-top:10px; }
.hf-composer__bar-spacer{ flex:1; }
.hf-composer__attach{ width:34px; height:34px; border-radius:var(--hf-radius-pill);
  border:1px solid var(--hf-border); background:var(--hf-surface-2); color:var(--hf-text-secondary);
  cursor:pointer; display:flex; align-items:center; justify-content:center; flex-shrink:0; }
.hf-composer__attach:hover{ color:var(--hf-text-primary); border-color:var(--hf-border-strong); }
.hf-composer__attach svg{ width:17px; height:17px; }
.hf-composer__enhance{ display:inline-flex; align-items:center; gap:7px; height:34px; padding:0 12px;
  border-radius:var(--hf-radius-pill); border:1px solid var(--hf-border); background:var(--hf-surface-2);
  color:var(--hf-text-secondary); font:600 12px var(--hf-font-sans); cursor:pointer; }
.hf-composer__enhance svg{ width:14px; height:14px; color:var(--hf-accent); }
.hf-composer__go{ flex-shrink:0; width:40px; height:40px; border-radius:999px; border:none; cursor:pointer;
  background:var(--hf-action); color:var(--hf-action-fg); display:flex; align-items:center; justify-content:center;
  transition:background var(--hf-dur-fast) var(--hf-ease-out), transform var(--hf-dur-fast) var(--hf-ease-out); }
.hf-composer__go:hover{ background:var(--hf-action-hover); }
.hf-composer__go:active{ transform:scale(.94); }
.hf-composer__go:disabled{ background:var(--hf-action-disabled); color:var(--hf-text-disabled); cursor:not-allowed; }
.hf-composer__go svg{ width:18px; height:18px; }
`;
let injected = false;
function ensure() {
  if (injected || typeof document === 'undefined') return;
  const s = document.createElement('style');
  s.id = 'hf-composer-css';
  s.textContent = CSS;
  document.head.appendChild(s);
  injected = true;
}
function PromptComposer({
  placeholder = 'Describe the scene you want to create…',
  model = 'Seedance 2.0',
  modelIsNew = false,
  value,
  defaultValue = '',
  references = [],
  onSubmit,
  onModelClick,
  controls,
  enhance = true,
  className = '',
  ...rest
}) {
  ensure();
  const isControlled = value !== undefined;
  const [internal, setInternal] = React.useState(defaultValue);
  const text = isControlled ? value : internal;
  const [focus, setFocus] = React.useState(false);
  const set = v => {
    if (!isControlled) setInternal(v);
    rest.onChange && rest.onChange(v);
  };
  const submit = () => {
    if (text && text.trim()) onSubmit && onSubmit(text);
  };
  return /*#__PURE__*/React.createElement("div", {
    className: 'hf-composer' + (focus ? ' hf-composer--focus' : '') + (className ? ' ' + className : '')
  }, references.length > 0 && /*#__PURE__*/React.createElement("div", {
    className: "hf-composer__refs"
  }, references.map((r, i) => /*#__PURE__*/React.createElement("div", {
    className: "hf-composer__ref",
    key: i
  }, r.src && /*#__PURE__*/React.createElement("img", {
    src: r.src,
    alt: ""
  }), /*#__PURE__*/React.createElement("button", {
    className: "hf-composer__ref-x",
    onClick: () => r.onRemove && r.onRemove(i),
    "aria-label": "Remove reference"
  }, /*#__PURE__*/React.createElement("svg", {
    width: "9",
    height: "9",
    viewBox: "0 0 9 9",
    fill: "none"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M2 2l5 5M7 2l-5 5",
    stroke: "currentColor",
    strokeWidth: "1.4",
    strokeLinecap: "round"
  })))))), /*#__PURE__*/React.createElement("textarea", {
    className: "hf-composer__input",
    placeholder: placeholder,
    rows: 2,
    value: text,
    onChange: e => set(e.target.value),
    onFocus: () => setFocus(true),
    onBlur: () => setFocus(false),
    onKeyDown: e => {
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        submit();
      }
    }
  }), /*#__PURE__*/React.createElement("div", {
    className: "hf-composer__bar"
  }, /*#__PURE__*/React.createElement("button", {
    className: "hf-composer__attach",
    "aria-label": "Add reference"
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 18 18",
    fill: "none"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M9 4v10M4 9h10",
    stroke: "currentColor",
    strokeWidth: "1.7",
    strokeLinecap: "round"
  }))), /*#__PURE__*/React.createElement(__ds_scope.ModelPill, {
    name: model,
    isNew: modelIsNew,
    onClick: onModelClick
  }), controls, /*#__PURE__*/React.createElement("div", {
    className: "hf-composer__bar-spacer"
  }), enhance && /*#__PURE__*/React.createElement("button", {
    className: "hf-composer__enhance"
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 14 14",
    fill: "currentColor"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M7 0l1.2 3.9L12 5 8.2 6.1 7 10 5.8 6.1 2 5l3.8-1.1z"
  })), "Enhance"), /*#__PURE__*/React.createElement("button", {
    className: "hf-composer__go",
    onClick: submit,
    disabled: !text || !text.trim(),
    "aria-label": "Generate"
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 18 18",
    fill: "none"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M9 15V3M4 8l5-5 5 5",
    stroke: "currentColor",
    strokeWidth: "1.9",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  })))));
}
Object.assign(__ds_scope, { PromptComposer });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/media/PromptComposer.jsx", error: String((e && e.message) || e) }); }

// ui_kits/web-app/CreateView.jsx
try { (() => {
/* Higgsfield web-app — Create workspace: settings rail + generation canvas */
function CreateView({
  prompt,
  model,
  onOpenModels,
  onBack
}) {
  const {
    PromptComposer,
    Card,
    Select,
    SegmentedControl,
    Slider,
    Switch,
    Button,
    MediaCard,
    Spinner,
    Badge
  } = window.HiggsfieldDesignSystem_b4c079;
  const D = window.HF_DATA;
  const [status, setStatus] = React.useState('idle'); // idle | generating | done
  const [results, setResults] = React.useState([]);
  const [text, setText] = React.useState(prompt || '');
  const run = p => {
    setText(p || text);
    setStatus('generating');
    setResults([]);
    setTimeout(() => {
      const pick = ['drift', 'storm', 'orbital', 'redcarpet'];
      setResults(pick.map((img, i) => ({
        img,
        label: (p || text || 'Generation').slice(0, 22),
        i
      })));
      setStatus('done');
    }, 2600);
  };
  React.useEffect(() => {
    if (prompt) run(prompt); /* auto-run when arriving with a prompt */
  }, []);
  return /*#__PURE__*/React.createElement("div", {
    className: "hfk-create"
  }, /*#__PURE__*/React.createElement("aside", {
    className: "hfk-create__panel"
  }, /*#__PURE__*/React.createElement("button", {
    className: "hfk-create__back",
    onClick: onBack
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "chevronDown",
    size: 16,
    style: {
      transform: 'rotate(90deg)'
    }
  }), " Explore"), /*#__PURE__*/React.createElement(Card, {
    title: "Settings",
    className: "hfk-create__settings"
  }, /*#__PURE__*/React.createElement("div", {
    className: "hfk-field"
  }, /*#__PURE__*/React.createElement("label", null, "Model"), /*#__PURE__*/React.createElement("button", {
    className: "hfk-modelrow",
    onClick: onOpenModels
  }, /*#__PURE__*/React.createElement("span", {
    className: "hfk-modelrow__mark"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "spark",
    size: 12,
    fill: true
  })), /*#__PURE__*/React.createElement("span", null, model), /*#__PURE__*/React.createElement(Badge, {
    variant: "new",
    uppercase: true
  }, "New"), /*#__PURE__*/React.createElement(Icon, {
    name: "chevronDown",
    size: 15,
    style: {
      marginLeft: 'auto',
      opacity: .5
    }
  }))), /*#__PURE__*/React.createElement("div", {
    className: "hfk-field"
  }, /*#__PURE__*/React.createElement("label", null, "Aspect ratio"), /*#__PURE__*/React.createElement(SegmentedControl, {
    size: "sm",
    options: D.ratios,
    defaultValue: "16:9"
  })), /*#__PURE__*/React.createElement("div", {
    className: "hfk-field"
  }, /*#__PURE__*/React.createElement("label", null, "Resolution"), /*#__PURE__*/React.createElement(Select, {
    options: ['1080p', 'Native 4K', '720p'],
    defaultValue: "Native 4K",
    style: {
      width: '100%'
    }
  })), /*#__PURE__*/React.createElement(Slider, {
    label: "Duration",
    min: 3,
    max: 12,
    defaultValue: 5,
    suffix: "s"
  }), /*#__PURE__*/React.createElement(Slider, {
    label: "Motion intensity",
    tone: "accent",
    defaultValue: 55,
    suffix: "%"
  }), /*#__PURE__*/React.createElement("div", {
    className: "hfk-field"
  }, /*#__PURE__*/React.createElement("label", null, "Camera controls"), /*#__PURE__*/React.createElement("div", {
    className: "hfk-switches"
  }, /*#__PURE__*/React.createElement(Switch, {
    label: "Crash zoom",
    defaultChecked: true
  }), /*#__PURE__*/React.createElement(Switch, {
    label: "Bullet time"
  }), /*#__PURE__*/React.createElement(Switch, {
    label: "Dolly",
    tone: "white"
  }))))), /*#__PURE__*/React.createElement("main", {
    className: "hfk-create__stage"
  }, /*#__PURE__*/React.createElement("div", {
    className: "hfk-canvas"
  }, status === 'idle' && /*#__PURE__*/React.createElement("div", {
    className: "hfk-canvas__empty"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "film",
    size: 34
  }), /*#__PURE__*/React.createElement("p", null, "Your renders will appear here")), status === 'generating' && /*#__PURE__*/React.createElement("div", {
    className: "hfk-canvas__loading"
  }, /*#__PURE__*/React.createElement(Spinner, {
    size: "lg",
    accent: true
  }), /*#__PURE__*/React.createElement("p", null, "Rendering on ", model, "\u2026"), /*#__PURE__*/React.createElement("span", null, "Stacking VFX \xB7 native 4K \xB7 ~30s")), status === 'done' && /*#__PURE__*/React.createElement("div", {
    className: "hfk-results"
  }, results.map(r => /*#__PURE__*/React.createElement(MediaCard, {
    key: r.i,
    label: r.label,
    model: model,
    badge: "4K",
    ratio: "16:9",
    showPlay: true,
    src: D.base + r.img + '.jpg'
  })))), /*#__PURE__*/React.createElement("div", {
    className: "hfk-create__composer"
  }, /*#__PURE__*/React.createElement(PromptComposer, {
    model: model,
    modelIsNew: true,
    value: text,
    onChange: setText,
    onModelClick: onOpenModels,
    onSubmit: run,
    placeholder: "Describe your shot \u2014 camera, lighting, mood\u2026"
  }))));
}
window.CreateView = CreateView;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/web-app/CreateView.jsx", error: String((e && e.message) || e) }); }

// ui_kits/web-app/ExploreView.jsx
try { (() => {
/* Higgsfield web-app — Explore / home view: hero composer + preset galleries */
function ExploreView({
  mode,
  onGenerate,
  onOpenModels,
  model
}) {
  const {
    PromptComposer,
    MediaCard,
    SegmentedControl,
    Tag,
    Badge
  } = window.HiggsfieldDesignSystem_b4c079;
  const D = window.HF_DATA;
  const [filter, setFilter] = React.useState('All');
  const filters = ['All', 'Cinematic', 'VFX', 'Portrait', 'Anime', '3D', 'Product'];
  return /*#__PURE__*/React.createElement("div", {
    className: "hfk-explore"
  }, /*#__PURE__*/React.createElement("section", {
    className: "hfk-hero"
  }, /*#__PURE__*/React.createElement("div", {
    className: "hfk-hero__eyebrow"
  }, /*#__PURE__*/React.createElement(Badge, {
    variant: "new",
    uppercase: true
  }, "New"), /*#__PURE__*/React.createElement("span", null, "Seedance 2.0 \u2014 native 4K video is here")), /*#__PURE__*/React.createElement("h1", {
    className: "hfk-hero__title"
  }, "What will you create today?"), /*#__PURE__*/React.createElement("p", {
    className: "hfk-hero__sub"
  }, "Generate cinematic ", mode.toLowerCase(), " from a prompt or reference. Big-budget VFX, no camera required."), /*#__PURE__*/React.createElement("div", {
    className: "hfk-hero__composer"
  }, /*#__PURE__*/React.createElement(PromptComposer, {
    model: model,
    modelIsNew: true,
    placeholder: `Describe the ${mode.toLowerCase()} you want to create…`,
    onModelClick: onOpenModels,
    onSubmit: onGenerate,
    controls: /*#__PURE__*/React.createElement(SegmentedControl, {
      size: "sm",
      options: D.ratios,
      defaultValue: "16:9"
    })
  }))), /*#__PURE__*/React.createElement("section", {
    className: "hfk-section"
  }, /*#__PURE__*/React.createElement("div", {
    className: "hfk-section__head"
  }, /*#__PURE__*/React.createElement("h2", null, "Viral presets"), /*#__PURE__*/React.createElement("span", {
    className: "hfk-section__link"
  }, "View all \u2192")), /*#__PURE__*/React.createElement("div", {
    className: "hfk-filters"
  }, filters.map(f => /*#__PURE__*/React.createElement(Tag, {
    key: f,
    onClick: () => setFilter(f),
    selected: filter === f
  }, f))), /*#__PURE__*/React.createElement("div", {
    className: "hfk-grid hfk-grid--3"
  }, D.presets.map((p, i) => /*#__PURE__*/React.createElement(MediaCard, {
    key: i,
    label: p.label,
    model: p.model,
    author: p.author,
    badge: p.badge,
    ratio: "16:9",
    showPlay: true,
    src: D.base + p.img + '.jpg',
    onClick: () => onGenerate(p.label)
  })))), /*#__PURE__*/React.createElement("section", {
    className: "hfk-section"
  }, /*#__PURE__*/React.createElement("div", {
    className: "hfk-section__head"
  }, /*#__PURE__*/React.createElement("h2", null, "Seedance 2.0 \xB7 4K community"), /*#__PURE__*/React.createElement("span", {
    className: "hfk-section__link"
  }, "View all \u2192")), /*#__PURE__*/React.createElement("div", {
    className: "hfk-grid hfk-grid--vert"
  }, D.vertical.concat(D.vertical).map((p, i) => /*#__PURE__*/React.createElement(MediaCard, {
    key: i,
    label: p.label,
    model: p.model,
    badge: p.badge,
    ratio: "9:16",
    showPlay: true,
    src: D.base + p.img + '.jpg',
    onClick: () => onGenerate(p.label)
  })))));
}
window.ExploreView = ExploreView;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/web-app/ExploreView.jsx", error: String((e && e.message) || e) }); }

// ui_kits/web-app/Sidebar.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/* Higgsfield web-app — left navigation rail */
function Sidebar({
  active,
  onNavigate
}) {
  const {
    Badge,
    Avatar
  } = window.HiggsfieldDesignSystem_b4c079;
  const D = window.HF_DATA;
  const Item = ({
    id,
    label,
    icon,
    isNew,
    onClick,
    activeId
  }) => /*#__PURE__*/React.createElement("button", {
    className: 'hfk-side__item' + (activeId === id ? ' is-active' : ''),
    onClick: onClick
  }, /*#__PURE__*/React.createElement(Icon, {
    name: icon,
    size: 19
  }), /*#__PURE__*/React.createElement("span", {
    className: "hfk-side__label"
  }, label), isNew && /*#__PURE__*/React.createElement(Badge, {
    variant: "new",
    uppercase: true
  }, "New"));
  return /*#__PURE__*/React.createElement("aside", {
    className: "hfk-side"
  }, /*#__PURE__*/React.createElement("div", {
    className: "hfk-side__brand"
  }, /*#__PURE__*/React.createElement("span", {
    className: "hfk-side__mark"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "spark",
    size: 17,
    fill: true
  })), /*#__PURE__*/React.createElement("span", {
    className: "hfk-side__word"
  }, "Higgsfield")), /*#__PURE__*/React.createElement("div", {
    className: "hfk-side__group"
  }, D.nav.map(n => /*#__PURE__*/React.createElement(Item, _extends({
    key: n.id
  }, n, {
    activeId: active,
    onClick: () => onNavigate(n.id)
  })))), /*#__PURE__*/React.createElement("div", {
    className: "hfk-side__heading"
  }, "Studios"), /*#__PURE__*/React.createElement("div", {
    className: "hfk-side__group"
  }, D.tools.map(t => /*#__PURE__*/React.createElement(Item, {
    key: t.id,
    id: t.id,
    label: t.label,
    icon: t.id === 'marketing' ? 'megaphone' : t.id === 'cinema' ? 'film' : t.id === 'influencer' ? 'users' : 'cpu',
    isNew: t.isNew,
    activeId: active,
    onClick: () => onNavigate(t.id)
  }))), /*#__PURE__*/React.createElement("div", {
    className: "hfk-side__spacer"
  }), /*#__PURE__*/React.createElement("button", {
    className: "hfk-side__upgrade",
    onClick: () => onNavigate('upgrade')
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "crown",
    size: 17
  }), /*#__PURE__*/React.createElement("div", {
    className: "hfk-side__upgrade-txt"
  }, /*#__PURE__*/React.createElement("strong", null, "Upgrade to Pro"), /*#__PURE__*/React.createElement("span", null, "Unlimited 4K renders"))), /*#__PURE__*/React.createElement("button", {
    className: "hfk-side__user",
    onClick: () => onNavigate('profile')
  }, /*#__PURE__*/React.createElement(Avatar, {
    name: "Ada Wong",
    size: "sm"
  }), /*#__PURE__*/React.createElement("div", {
    className: "hfk-side__user-txt"
  }, /*#__PURE__*/React.createElement("strong", null, "Ada Wong"), /*#__PURE__*/React.createElement("span", null, "240 credits"))));
}
window.Sidebar = Sidebar;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/web-app/Sidebar.jsx", error: String((e && e.message) || e) }); }

// ui_kits/web-app/TopBar.jsx
try { (() => {
/* Higgsfield web-app — top bar with search, mode segmented + credits */
function TopBar({
  mode,
  onMode,
  query,
  onQuery
}) {
  const {
    SegmentedControl,
    IconButton,
    Badge
  } = window.HiggsfieldDesignSystem_b4c079;
  return /*#__PURE__*/React.createElement("header", {
    className: "hfk-top"
  }, /*#__PURE__*/React.createElement("div", {
    className: "hfk-top__search"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "search",
    size: 18,
    className: "hfk-top__search-i"
  }), /*#__PURE__*/React.createElement("input", {
    placeholder: "Search 200+ viral presets, models and styles",
    value: query,
    onChange: e => onQuery(e.target.value)
  }), /*#__PURE__*/React.createElement("kbd", null, "/")), /*#__PURE__*/React.createElement(SegmentedControl, {
    options: [{
      value: 'Image',
      label: 'Image',
      icon: /*#__PURE__*/React.createElement(Icon, {
        name: "image",
        size: 15
      })
    }, {
      value: 'Video',
      label: 'Video',
      icon: /*#__PURE__*/React.createElement(Icon, {
        name: "video",
        size: 15
      })
    }, {
      value: 'Audio',
      label: 'Audio',
      icon: /*#__PURE__*/React.createElement(Icon, {
        name: "audio",
        size: 15
      })
    }],
    value: mode,
    onChange: onMode
  }), /*#__PURE__*/React.createElement("div", {
    className: "hfk-top__right"
  }, /*#__PURE__*/React.createElement("span", {
    className: "hfk-top__credits"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "spark",
    size: 14,
    fill: true
  }), " 240"), /*#__PURE__*/React.createElement(IconButton, {
    variant: "ghost",
    "aria-label": "Notifications"
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "bell",
    size: 19
  }))));
}
window.TopBar = TopBar;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/web-app/TopBar.jsx", error: String((e && e.message) || e) }); }

// ui_kits/web-app/data.js
try { (() => {
// Higgsfield web-app UI kit — demo data (placeholder media live in assets/placeholders)
window.HF_DATA = {
  models: [{
    name: 'Seedance 2.0',
    kind: 'Video',
    isNew: true,
    desc: 'High-quality 4K video in seconds'
  }, {
    name: 'Sora 2',
    kind: 'Video',
    desc: "OpenAI's flagship video model"
  }, {
    name: 'Kling 3.0',
    kind: 'Video',
    desc: 'Expressive motion & camera control'
  }, {
    name: 'Veo 3.1',
    kind: 'Video',
    desc: 'Google DeepMind cinematic video'
  }, {
    name: 'Soul 2.0',
    kind: 'Image',
    isNew: true,
    desc: 'Photoreal images with Soul ID'
  }, {
    name: 'Nano Banana Pro',
    kind: 'Image',
    desc: 'Accurate text & UI rendering'
  }],
  nav: [{
    id: 'explore',
    label: 'Explore',
    icon: 'compass'
  }, {
    id: 'create',
    label: 'Create',
    icon: 'spark'
  }, {
    id: 'library',
    label: 'Library',
    icon: 'grid'
  }, {
    id: 'canvas',
    label: 'Canvas',
    icon: 'nodes',
    isNew: true
  }],
  tools: [{
    id: 'marketing',
    label: 'Marketing Studio'
  }, {
    id: 'cinema',
    label: 'Cinema Studio'
  }, {
    id: 'influencer',
    label: 'AI Influencer'
  }, {
    id: 'supercomputer',
    label: 'Supercomputer',
    isNew: true
  }],
  presets: [{
    label: 'Drift Racing',
    model: 'Seedance 2.0',
    author: 'buralqy',
    img: 'drift',
    badge: '4K',
    ratio: '16:9'
  }, {
    label: 'Neon City',
    model: 'Soul 2.0',
    img: 'neon',
    ratio: '16:9'
  }, {
    label: 'Kung Fu Hit',
    model: 'Seedance 2.0',
    author: 'buralqy',
    img: 'kungfu',
    ratio: '16:9'
  }, {
    label: 'Storm Giant',
    model: 'Veo 3.1',
    img: 'storm',
    badge: '4K',
    ratio: '16:9'
  }, {
    label: "2000's Paparazzi",
    model: 'Soul 2.0',
    author: 'buralqy',
    img: 'paparazzi',
    ratio: '16:9'
  }, {
    label: 'Golf Major',
    model: 'Seedance 2.0',
    img: 'golf',
    ratio: '16:9'
  }, {
    label: 'Orbital Presence',
    model: 'Kling 3.0',
    author: 'buralqy',
    img: 'orbital',
    ratio: '16:9'
  }, {
    label: 'Red Carpet',
    model: 'Soul 2.0',
    img: 'redcarpet',
    badge: '4K',
    ratio: '16:9'
  }, {
    label: 'Zombie Dance',
    model: 'Seedance 2.0',
    author: 'buralqy',
    img: 'zombie',
    ratio: '16:9'
  }],
  vertical: [{
    label: 'Free Fall',
    model: 'Seedance 2.0',
    img: 'freefall',
    ratio: '9:16',
    badge: '4K'
  }, {
    label: 'Nightline',
    model: 'Kling 3.0',
    img: 'nightline',
    ratio: '9:16'
  }, {
    label: 'Soul Fighter',
    model: 'Soul 2.0',
    img: 'soulfighter',
    ratio: '9:16'
  }],
  ratios: ['16:9', '9:16', '1:1', '4:5'],
  base: '../../assets/placeholders/'
};
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/web-app/data.js", error: String((e && e.message) || e) }); }

// ui_kits/web-app/icons.jsx
try { (() => {
/* Higgsfield web-app kit — icon set.
   Paths are from Lucide (ISC) — the closest CDN match to Higgsfield's
   custom line icons. stroke = currentColor, 24px grid. */
const HF_ICON_PATHS = {
  compass: '<circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>',
  spark: '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .962 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.962 0z"/><path d="M20 3v4"/><path d="M22 5h-4"/><path d="M4 17v2"/><path d="M5 18H3"/>',
  grid: '<rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/>',
  nodes: '<rect width="8" height="8" x="3" y="3" rx="2"/><path d="M7 11v4a2 2 0 0 0 2 2h4"/><rect width="8" height="8" x="13" y="13" rx="2"/>',
  image: '<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>',
  video: '<path d="m16 13 5.223 3.482a.5.5 0 0 0 .777-.416V7.87a.5.5 0 0 0-.752-.432L16 10.5"/><rect x="2" y="6" width="14" height="12" rx="2"/>',
  audio: '<path d="M2 10v3"/><path d="M6 6v11"/><path d="M10 3v18"/><path d="M14 8v7"/><path d="M18 5v13"/><path d="M22 10v3"/>',
  search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
  sliders: '<path d="M20 7h-9"/><path d="M14 17H5"/><circle cx="17" cy="17" r="3"/><circle cx="7" cy="7" r="3"/>',
  bell: '<path d="M10.268 21a2 2 0 0 0 3.464 0"/><path d="M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326"/>',
  user: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
  chevronDown: '<path d="m6 9 6 6 6-6"/>',
  play: '<polygon points="6 3 20 12 6 21 6 3"/>',
  heart: '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
  more: '<circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>',
  x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  wand: '<path d="m12 3-1.9 5.8a2 2 0 0 1-1.287 1.288L3 12l5.8 1.9a2 2 0 0 1 1.288 1.287L12 21l1.9-5.8a2 2 0 0 1 1.287-1.288L21 12l-5.8-1.9a2 2 0 0 1-1.288-1.287Z"/>',
  folder: '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
  crown: '<path d="M11.562 3.266a.5.5 0 0 1 .876 0L15.39 8.87a1 1 0 0 0 1.516.294L21.183 5.5a.5.5 0 0 1 .798.519l-2.834 10.246a1 1 0 0 1-.956.734H5.81a1 1 0 0 1-.957-.734L2.02 6.02a.5.5 0 0 1 .798-.519l4.276 3.664a1 1 0 0 0 1.516-.294z"/>',
  arrowUp: '<path d="m5 12 7-7 7 7"/><path d="M12 19V5"/>',
  film: '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M7 3v18"/><path d="M3 7.5h4"/><path d="M3 12h18"/><path d="M3 16.5h4"/><path d="M17 3v18"/><path d="M17 7.5h4"/><path d="M17 16.5h4"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  megaphone: '<path d="m3 11 18-5v12L3 14v-3z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  cpu: '<rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/><path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/>'
};
function Icon({
  name,
  size = 20,
  fill = false,
  stroke = 2,
  className = '',
  style = {}
}) {
  const inner = HF_ICON_PATHS[name] || '';
  return React.createElement('svg', {
    className,
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: fill ? 'currentColor' : 'none',
    stroke: fill ? 'none' : 'currentColor',
    strokeWidth: stroke,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    style: {
      display: 'block',
      flexShrink: 0,
      ...style
    },
    dangerouslySetInnerHTML: {
      __html: inner
    }
  });
}
window.Icon = Icon;
window.HF_ICON_PATHS = HF_ICON_PATHS;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/web-app/icons.jsx", error: String((e && e.message) || e) }); }

__ds_ns.Avatar = __ds_scope.Avatar;

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.Button = __ds_scope.Button;

__ds_ns.IconButton = __ds_scope.IconButton;

__ds_ns.Spinner = __ds_scope.Spinner;

__ds_ns.Tag = __ds_scope.Tag;

__ds_ns.Dialog = __ds_scope.Dialog;

__ds_ns.Toast = __ds_scope.Toast;

__ds_ns.ToastStack = __ds_scope.ToastStack;

__ds_ns.Tooltip = __ds_scope.Tooltip;

__ds_ns.Input = __ds_scope.Input;

__ds_ns.SegmentedControl = __ds_scope.SegmentedControl;

__ds_ns.Select = __ds_scope.Select;

__ds_ns.Slider = __ds_scope.Slider;

__ds_ns.Switch = __ds_scope.Switch;

__ds_ns.Card = __ds_scope.Card;

__ds_ns.MediaCard = __ds_scope.MediaCard;

__ds_ns.ModelPill = __ds_scope.ModelPill;

__ds_ns.PromptComposer = __ds_scope.PromptComposer;

})();
