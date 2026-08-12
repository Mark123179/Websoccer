/* @ds-bundle: {"format":3,"namespace":"WebsoccerDesignSystem_caf892","components":[{"name":"Badge","sourcePath":"components/core/Badge.jsx"},{"name":"Button","sourcePath":"components/core/Button.jsx"},{"name":"FormDots","sourcePath":"components/core/FormDots.jsx"},{"name":"IconButton","sourcePath":"components/core/IconButton.jsx"},{"name":"ProgressBar","sourcePath":"components/core/ProgressBar.jsx"},{"name":"StatusDot","sourcePath":"components/core/StatusDot.jsx"},{"name":"Tag","sourcePath":"components/core/Tag.jsx"},{"name":"ValuePill","sourcePath":"components/core/ValuePill.jsx"},{"name":"SearchField","sourcePath":"components/forms/SearchField.jsx"},{"name":"Avatar","sourcePath":"components/media/Avatar.jsx"},{"name":"Crest","sourcePath":"components/media/Crest.jsx"},{"name":"NavItem","sourcePath":"components/navigation/NavItem.jsx"},{"name":"Tabs","sourcePath":"components/navigation/Tabs.jsx"},{"name":"KpiCard","sourcePath":"components/surfaces/KpiCard.jsx"},{"name":"Panel","sourcePath":"components/surfaces/Panel.jsx"}],"sourceHashes":{"components/core/Badge.jsx":"0a65efa3a0a7","components/core/Button.jsx":"e658e2ac1666","components/core/FormDots.jsx":"f6dea1a55733","components/core/IconButton.jsx":"379a508542fb","components/core/ProgressBar.jsx":"2efe3b0f85cf","components/core/StatusDot.jsx":"9ed1c2711ab8","components/core/Tag.jsx":"64f70416c3cf","components/core/ValuePill.jsx":"d0e1db025e63","components/forms/SearchField.jsx":"d546658c2b16","components/media/Avatar.jsx":"41478fb165a9","components/media/Crest.jsx":"6b1b717b222a","components/navigation/NavItem.jsx":"1f219c23de6c","components/navigation/Tabs.jsx":"b8c35a060b66","components/surfaces/KpiCard.jsx":"8a41bcc21ada","components/surfaces/Panel.jsx":"3a7aa6784a33"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.WebsoccerDesignSystem_caf892 = window.WebsoccerDesignSystem_caf892 || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/core/Badge.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Badge — small count/notification chip (the orange nav counter)
 * or a status pill. tone: "count" (orange) | "cyan" | "green" | "neutral".
 */
function Badge({
  children,
  tone = "count",
  style = {},
  ...rest
}) {
  const tones = {
    count: {
      background: "linear-gradient(180deg, #ff9f1c, #d85d00)",
      border: "1px solid rgba(255, 228, 163, 0.78)",
      color: "#ffffff",
      boxShadow: "0 0 14px rgba(255, 122, 24, 0.34)"
    },
    cyan: {
      background: "var(--cyan)",
      border: "1px solid var(--cyan)",
      color: "var(--dark-text)"
    },
    green: {
      background: "rgba(48, 242, 156, 0.16)",
      border: "1px solid rgba(48, 242, 156, 0.5)",
      color: "var(--green)"
    },
    neutral: {
      background: "rgba(255, 255, 255, 0.06)",
      border: "1px solid var(--line)",
      color: "var(--muted)"
    }
  };
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      minWidth: 19,
      height: 19,
      padding: "0 6px",
      borderRadius: "var(--radius-pill)",
      fontFamily: "var(--font-sans)",
      fontSize: 11,
      fontWeight: 900,
      lineHeight: 1,
      ...tones[tone],
      ...style
    }
  }, rest), children);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Badge.jsx", error: String((e && e.message) || e) }); }

// components/core/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Websoccer Button — the command-center action.
 * Variants: primary (cyan gradient), secondary (glass), ghost, danger.
 * Sizes: sm | md | lg. Optional leading icon (pass any node).
 */
function Button({
  children,
  variant = "primary",
  size = "md",
  icon = null,
  disabled = false,
  fullWidth = false,
  type = "button",
  onClick,
  style = {},
  ...rest
}) {
  const sizes = {
    sm: {
      minHeight: 34,
      padding: "0 14px",
      fontSize: 13
    },
    md: {
      minHeight: 42,
      padding: "11px 18px",
      fontSize: 14
    },
    lg: {
      minHeight: 48,
      padding: "13px 24px",
      fontSize: 15
    }
  };
  const variants = {
    primary: {
      background: "linear-gradient(180deg, #1bd9ee, #06879a)",
      border: "1px solid rgba(93, 249, 255, 0.46)",
      color: "#ffffff"
    },
    secondary: {
      background: "rgba(255, 255, 255, 0.05)",
      border: "1px solid var(--line)",
      color: "var(--text)"
    },
    ghost: {
      background: "transparent",
      border: "1px solid var(--line)",
      color: "var(--muted)"
    },
    danger: {
      background: "linear-gradient(180deg, #ff7a92, #d8344f)",
      border: "1px solid rgba(255, 150, 168, 0.55)",
      color: "#ffffff"
    }
  };
  return /*#__PURE__*/React.createElement("button", _extends({
    type: type,
    disabled: disabled,
    onClick: onClick,
    style: {
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      gap: 8,
      width: fullWidth ? "100%" : "auto",
      borderRadius: "var(--radius)",
      fontFamily: "var(--font-sans)",
      fontWeight: 800,
      letterSpacing: 0.2,
      cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.45 : 1,
      transition: "filter .15s ease, transform .1s ease",
      ...sizes[size],
      ...variants[variant],
      ...style
    },
    onMouseDown: e => !disabled && (e.currentTarget.style.transform = "translateY(1px)"),
    onMouseUp: e => e.currentTarget.style.transform = "",
    onMouseLeave: e => e.currentTarget.style.transform = ""
  }, rest), icon && /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      width: 18,
      height: 18
    }
  }, icon), children);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Button.jsx", error: String((e && e.message) || e) }); }

// components/core/FormDots.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * FormDots — recent-form squares (S/U/N = Sieg/Unentschieden/Niederlage,
 * i.e. W/D/L). Pass an array of results.
 */
function FormDots({
  results = [],
  style = {},
  ...rest
}) {
  const palette = {
    S: {
      bg: "rgba(48, 242, 156, 0.18)",
      bd: "rgba(48, 242, 156, 0.5)",
      fg: "var(--green)"
    },
    U: {
      bg: "rgba(255, 209, 102, 0.16)",
      bd: "rgba(255, 209, 102, 0.5)",
      fg: "var(--yellow)"
    },
    N: {
      bg: "rgba(255, 85, 112, 0.16)",
      bd: "rgba(255, 85, 112, 0.5)",
      fg: "var(--red)"
    }
  };
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      display: "inline-flex",
      gap: 4,
      ...style
    }
  }, rest), results.map((r, i) => {
    const p = palette[r] || palette.U;
    return /*#__PURE__*/React.createElement("i", {
      key: i,
      style: {
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: 18,
        height: 18,
        borderRadius: 4,
        background: p.bg,
        border: `1px solid ${p.bd}`,
        color: p.fg,
        fontFamily: "var(--font-sans)",
        fontStyle: "normal",
        fontSize: 10,
        fontWeight: 900
      }
    }, r);
  }));
}
Object.assign(__ds_scope, { FormDots });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/FormDots.jsx", error: String((e && e.message) || e) }); }

// components/core/IconButton.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * IconButton — square glass button holding a single icon (top-bar
 * actions, nav quick-actions). Optional badge in the corner.
 */
function IconButton({
  children,
  badge,
  size = 42,
  ariaLabel,
  style = {},
  ...rest
}) {
  return /*#__PURE__*/React.createElement("button", _extends({
    type: "button",
    "aria-label": ariaLabel,
    style: {
      position: "relative",
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      width: size,
      height: size,
      borderRadius: "var(--radius)",
      background: "rgba(255, 255, 255, 0.052)",
      border: "1px solid var(--line)",
      color: "var(--cyan)",
      cursor: "pointer",
      transition: "background .15s ease, border-color .15s ease",
      ...style
    },
    onMouseEnter: e => {
      e.currentTarget.style.background = "var(--cyan-soft)";
      e.currentTarget.style.borderColor = "var(--line-strong)";
    },
    onMouseLeave: e => {
      e.currentTarget.style.background = "rgba(255, 255, 255, 0.052)";
      e.currentTarget.style.borderColor = "var(--line)";
    }
  }, rest), /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      width: 20,
      height: 20
    }
  }, children), badge != null && /*#__PURE__*/React.createElement("span", {
    style: {
      position: "absolute",
      top: -7,
      right: -6,
      minWidth: 18,
      height: 18,
      padding: "0 5px",
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      borderRadius: "var(--radius-pill)",
      background: "linear-gradient(180deg, #ff9f1c, #d85d00)",
      border: "1px solid rgba(255, 228, 163, 0.78)",
      boxShadow: "0 0 14px rgba(255, 122, 24, 0.34)",
      color: "#fff",
      fontFamily: "var(--font-sans)",
      fontSize: 11,
      fontWeight: 900,
      lineHeight: 1
    }
  }, badge));
}
Object.assign(__ds_scope, { IconButton });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/IconButton.jsx", error: String((e && e.message) || e) }); }

// components/core/ProgressBar.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * ProgressBar — thin track with a green→cyan fill, used for fitness,
 * morale, readiness ("Frische", "Fans"). value is 0–100.
 */
function ProgressBar({
  value = 0,
  height = 7,
  style = {},
  ...rest
}) {
  const pct = Math.max(0, Math.min(100, value));
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      display: "block",
      position: "relative",
      height,
      borderRadius: "var(--radius-pill)",
      background: "rgba(255, 255, 255, 0.08)",
      overflow: "hidden",
      ...style
    },
    role: "progressbar",
    "aria-valuenow": pct,
    "aria-valuemin": 0,
    "aria-valuemax": 100
  }, rest), /*#__PURE__*/React.createElement("span", {
    style: {
      position: "absolute",
      inset: "0 auto 0 0",
      width: `${pct}%`,
      borderRadius: "inherit",
      background: "linear-gradient(90deg, var(--green), var(--cyan))"
    }
  }));
}
Object.assign(__ds_scope, { ProgressBar });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/ProgressBar.jsx", error: String((e && e.message) || e) }); }

// components/core/StatusDot.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * StatusDot — small online/status indicator with optional label.
 * tone: "online" (green) | "live" | "off".
 */
function StatusDot({
  label,
  tone = "online",
  style = {},
  ...rest
}) {
  const tones = {
    online: "var(--green)",
    live: "var(--red)",
    off: "var(--text-muted)"
  };
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 7,
      fontFamily: "var(--font-sans)",
      fontSize: 12,
      fontWeight: 700,
      color: "var(--muted)",
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("i", {
    style: {
      width: 8,
      height: 8,
      borderRadius: "var(--radius-pill)",
      background: tones[tone],
      boxShadow: `0 0 8px ${tones[tone]}`
    }
  }), label);
}
Object.assign(__ds_scope, { StatusDot });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/StatusDot.jsx", error: String((e && e.message) || e) }); }

// components/core/Tag.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Tag — position / role badge (e.g. "ST", "OM", "1. Bundesliga").
 * tone: "cyan" (default) | "green" | "neutral" | "yellow" | "red".
 */
function Tag({
  children,
  tone = "cyan",
  style = {},
  ...rest
}) {
  const tones = {
    cyan: {
      bg: "rgba(34, 230, 255, 0.14)",
      bd: "rgba(34, 230, 255, 0.38)",
      fg: "var(--cyan)"
    },
    green: {
      bg: "rgba(48, 242, 156, 0.12)",
      bd: "rgba(48, 242, 156, 0.28)",
      fg: "var(--green)"
    },
    yellow: {
      bg: "rgba(255, 209, 102, 0.14)",
      bd: "rgba(255, 209, 102, 0.4)",
      fg: "var(--yellow)"
    },
    red: {
      bg: "rgba(255, 85, 112, 0.14)",
      bd: "rgba(255, 85, 112, 0.4)",
      fg: "var(--red)"
    },
    neutral: {
      bg: "rgba(255, 255, 255, 0.05)",
      bd: "var(--line)",
      fg: "var(--muted)"
    }
  };
  const t = tones[tone];
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 6,
      padding: "5px 9px",
      borderRadius: "var(--radius-sm)",
      background: t.bg,
      border: `1px solid ${t.bd}`,
      color: t.fg,
      fontFamily: "var(--font-sans)",
      fontSize: 12,
      fontWeight: 900,
      lineHeight: 1,
      whiteSpace: "nowrap",
      ...style
    }
  }, rest), children);
}
Object.assign(__ds_scope, { Tag });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Tag.jsx", error: String((e && e.message) || e) }); }

// components/core/ValuePill.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * ValuePill — green money / market-value chip (e.g. "140.000.000 €").
 */
function ValuePill({
  children,
  style = {},
  ...rest
}) {
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      display: "inline-flex",
      alignItems: "center",
      padding: "7px 9px",
      borderRadius: "var(--radius-sm)",
      background: "rgba(48, 242, 156, 0.12)",
      border: "1px solid rgba(48, 242, 156, 0.28)",
      color: "var(--green)",
      fontFamily: "var(--font-sans)",
      fontSize: 12,
      fontWeight: 900,
      lineHeight: 1,
      whiteSpace: "nowrap",
      ...style
    }
  }, rest), children);
}
Object.assign(__ds_scope, { ValuePill });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/ValuePill.jsx", error: String((e && e.message) || e) }); }

// components/forms/SearchField.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * SearchField — the glass search input with the brand magnifier
 * glyph. Cyan focus glow. Controlled or uncontrolled.
 */
function SearchField({
  placeholder = "Suchen",
  value,
  defaultValue,
  onChange,
  style = {},
  ...rest
}) {
  const [focus, setFocus] = React.useState(false);
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      display: "grid",
      gridTemplateColumns: "20px minmax(0, 1fr)",
      alignItems: "center",
      gap: 8,
      minHeight: 36,
      padding: "0 11px",
      borderRadius: "var(--radius)",
      background: focus ? "rgba(34, 230, 255, 0.08)" : "rgba(255, 255, 255, 0.052)",
      border: `1px solid ${focus ? "var(--line-strong)" : "var(--line)"}`,
      boxShadow: focus ? "0 0 18px rgba(34, 230, 255, 0.12)" : "none",
      transition: "background .15s, border-color .15s, box-shadow .15s",
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("span", {
    style: {
      position: "relative",
      width: 15,
      height: 15,
      border: "2px solid var(--cyan)",
      borderRadius: "var(--radius-pill)"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      position: "absolute",
      right: -5,
      top: 10,
      width: 2,
      height: 7,
      background: "var(--cyan)",
      borderRadius: "var(--radius-pill)",
      transform: "rotate(45deg)"
    }
  })), /*#__PURE__*/React.createElement("input", {
    type: "search",
    placeholder: placeholder,
    value: value,
    defaultValue: defaultValue,
    onChange: onChange,
    onFocus: () => setFocus(true),
    onBlur: () => setFocus(false),
    style: {
      width: "100%",
      minWidth: 0,
      background: "transparent",
      border: 0,
      outline: 0,
      color: "var(--text)",
      fontFamily: "var(--font-sans)",
      fontSize: 13,
      fontWeight: 700
    }
  }));
}
Object.assign(__ds_scope, { SearchField });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/SearchField.jsx", error: String((e && e.message) || e) }); }

// components/media/Avatar.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Avatar — square player/manager portrait with hairline border.
 * shape: "rounded" (default, 8px) | "circle". Optional jersey number.
 */
function Avatar({
  src,
  alt = "",
  size = 44,
  shape = "rounded",
  number,
  style = {},
  ...rest
}) {
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      position: "relative",
      display: "inline-block",
      width: size,
      height: size,
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("img", {
    src: src,
    alt: alt,
    style: {
      width: size,
      height: size,
      objectFit: "cover",
      objectPosition: "center top",
      borderRadius: shape === "circle" ? "50%" : "var(--radius)",
      background: "rgba(255, 255, 255, 0.06)",
      border: "1px solid var(--line-strong)",
      display: "block"
    }
  }), number != null && /*#__PURE__*/React.createElement("span", {
    style: {
      position: "absolute",
      bottom: -6,
      right: -6,
      minWidth: 20,
      height: 20,
      padding: "0 5px",
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      borderRadius: "var(--radius-sm)",
      background: "var(--cyan)",
      color: "var(--dark-text)",
      fontFamily: "var(--font-sans)",
      fontSize: 12,
      fontWeight: 900
    }
  }, number));
}
Object.assign(__ds_scope, { Avatar });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/media/Avatar.jsx", error: String((e && e.message) || e) }); }

// components/media/Crest.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Crest — club crest with the signature cyan drop-shadow glow.
 * Pass src (path to a crest png). size in px.
 */
function Crest({
  src,
  alt = "",
  size = 56,
  glow = true,
  style = {},
  ...rest
}) {
  return /*#__PURE__*/React.createElement("img", _extends({
    src: src,
    alt: alt,
    style: {
      width: size,
      height: size,
      objectFit: "contain",
      filter: glow ? "drop-shadow(0 0 18px rgba(34, 230, 255, 0.28))" : "none",
      ...style
    }
  }, rest));
}
Object.assign(__ds_scope, { Crest });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/media/Crest.jsx", error: String((e && e.message) || e) }); }

// components/navigation/NavItem.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * NavItem — a sidebar navigation link: icon chip + label, with the
 * brand's active state (cyan gradient fill + inset left bar).
 * Pass `icon` (a node) and `active`.
 */
function NavItem({
  icon,
  children,
  active = false,
  href = "#",
  style = {},
  ...rest
}) {
  return /*#__PURE__*/React.createElement("a", _extends({
    href: href,
    "aria-current": active ? "page" : undefined,
    style: {
      display: "flex",
      alignItems: "center",
      gap: 10,
      minHeight: 40,
      padding: "0 11px",
      borderRadius: "var(--radius)",
      border: `1px solid ${active ? "var(--line-strong)" : "transparent"}`,
      background: active ? "linear-gradient(90deg, rgba(34, 230, 255, 0.2), rgba(34, 230, 255, 0.06))" : "transparent",
      boxShadow: active ? "inset 3px 0 0 var(--cyan)" : "none",
      color: active ? "var(--text)" : "var(--muted)",
      fontFamily: "var(--font-sans)",
      fontSize: 15,
      fontWeight: 700,
      textDecoration: "none",
      transition: "background .15s, color .15s",
      ...style
    },
    onMouseEnter: e => {
      if (!active) e.currentTarget.style.color = "var(--text)";
    },
    onMouseLeave: e => {
      if (!active) e.currentTarget.style.color = "var(--muted)";
    }
  }, rest), icon && /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      width: 26,
      height: 26,
      borderRadius: 8,
      background: "rgba(255, 255, 255, 0.06)",
      color: "var(--cyan)",
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 18,
      height: 18,
      display: "inline-flex"
    }
  }, icon)), children);
}
Object.assign(__ds_scope, { NavItem });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/NavItem.jsx", error: String((e && e.message) || e) }); }

// components/navigation/Tabs.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Tabs — underlined segmented tabs used inside panels (e.g. squad
 * filters, profile sections). Controlled via value/onChange.
 */
function Tabs({
  tabs = [],
  value,
  onChange,
  style = {},
  ...rest
}) {
  const active = value ?? (tabs[0] && tabs[0].id);
  return /*#__PURE__*/React.createElement("div", _extends({
    role: "tablist",
    style: {
      display: "flex",
      gap: 6,
      borderBottom: "1px solid var(--line)",
      ...style
    }
  }, rest), tabs.map(t => {
    const on = t.id === active;
    return /*#__PURE__*/React.createElement("button", {
      key: t.id,
      role: "tab",
      "aria-selected": on,
      onClick: () => onChange && onChange(t.id),
      style: {
        position: "relative",
        padding: "9px 14px",
        background: "transparent",
        border: 0,
        cursor: "pointer",
        color: on ? "var(--text)" : "var(--muted)",
        fontFamily: "var(--font-sans)",
        fontSize: 13,
        fontWeight: 800,
        letterSpacing: 0.3,
        textTransform: "uppercase",
        boxShadow: on ? "inset 0 -2px 0 var(--cyan)" : "none"
      }
    }, t.label);
  }));
}
Object.assign(__ds_scope, { Tabs });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/Tabs.jsx", error: String((e && e.message) || e) }); }

// components/surfaces/KpiCard.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * KpiCard — compact metric tile: small uppercase label + big cyan
 * value, in its own glass panel. delta shows an optional green/red
 * change line.
 */
function KpiCard({
  label,
  value,
  delta,
  deltaTone = "green",
  style = {},
  ...rest
}) {
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      background: "var(--panel)",
      border: "1px solid var(--line)",
      borderRadius: "var(--radius)",
      boxShadow: "var(--shadow)",
      padding: 18,
      minHeight: 108,
      display: "flex",
      flexDirection: "column",
      justifyContent: "center",
      gap: 6,
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--faint)",
      fontFamily: "var(--font-sans)",
      fontSize: 12,
      fontWeight: 900,
      lineHeight: 1.4,
      textTransform: "uppercase"
    }
  }, label), /*#__PURE__*/React.createElement("strong", {
    style: {
      color: "var(--cyan)",
      fontFamily: "var(--font-sans)",
      fontSize: 24,
      fontWeight: 900,
      lineHeight: 1.15
    }
  }, value), delta != null && /*#__PURE__*/React.createElement("span", {
    style: {
      color: deltaTone === "red" ? "var(--red)" : "var(--green)",
      fontFamily: "var(--font-sans)",
      fontSize: 12,
      fontWeight: 800
    }
  }, delta));
}
Object.assign(__ds_scope, { KpiCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/surfaces/KpiCard.jsx", error: String((e && e.message) || e) }); }

// components/surfaces/Panel.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Panel — the brand's glass dashboard card. Optional uppercase
 * card title and right-aligned header action. variant "hero" adds
 * the top-right white spec gradient used on hero/VS/match cards.
 */
function Panel({
  title,
  action,
  variant = "default",
  children,
  padding = 18,
  style = {},
  ...rest
}) {
  const bg = variant === "hero" ? "linear-gradient(rgba(7, 20, 31, 0.88), rgba(5, 15, 23, 0.9)), radial-gradient(circle at 75% 15%, rgba(255, 255, 255, 0.16), transparent 22%)" : "var(--panel)";
  return /*#__PURE__*/React.createElement("section", _extends({
    style: {
      background: bg,
      border: "1px solid var(--line)",
      borderRadius: "var(--radius)",
      boxShadow: "var(--shadow)",
      padding,
      overflow: "hidden",
      ...style
    }
  }, rest), (title || action) && /*#__PURE__*/React.createElement("header", {
    style: {
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      marginBottom: 14
    }
  }, title && /*#__PURE__*/React.createElement("h3", {
    style: {
      margin: 0,
      color: "var(--text)",
      fontFamily: "var(--font-sans)",
      fontSize: 15,
      fontWeight: 900,
      letterSpacing: 0.7,
      textTransform: "uppercase"
    }
  }, title), action), children);
}
Object.assign(__ds_scope, { Panel });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/surfaces/Panel.jsx", error: String((e && e.message) || e) }); }

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.Button = __ds_scope.Button;

__ds_ns.FormDots = __ds_scope.FormDots;

__ds_ns.IconButton = __ds_scope.IconButton;

__ds_ns.ProgressBar = __ds_scope.ProgressBar;

__ds_ns.StatusDot = __ds_scope.StatusDot;

__ds_ns.Tag = __ds_scope.Tag;

__ds_ns.ValuePill = __ds_scope.ValuePill;

__ds_ns.SearchField = __ds_scope.SearchField;

__ds_ns.Avatar = __ds_scope.Avatar;

__ds_ns.Crest = __ds_scope.Crest;

__ds_ns.NavItem = __ds_scope.NavItem;

__ds_ns.Tabs = __ds_scope.Tabs;

__ds_ns.KpiCard = __ds_scope.KpiCard;

__ds_ns.Panel = __ds_scope.Panel;

})();
