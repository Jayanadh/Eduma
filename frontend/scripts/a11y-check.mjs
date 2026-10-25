// A static accessibility check over every component template (BUILD-12): images need alt text, buttons and links need
// a name, and every form control needs a label (a <label for>, an aria-label, or a wrapping <label>). It parses with
// Angular's own template parser, so @if/@for blocks and bindings are understood. Run: npm run check:a11y
import { parseTemplate } from '@angular/compiler';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = 'src/app';
const CONTROLS = new Set(['input', 'select', 'textarea']);
const UNLABELLED_INPUTS = new Set(['hidden', 'submit', 'button', 'reset']);

function files(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? files(path) : /\.(ts|html)$/.test(name) && !name.endsWith('.spec.ts') ? [path] : [];
  });
}

function templates(path) {
  const text = readFileSync(path, 'utf8');
  if (path.endsWith('.html')) return [text];
  return [...text.matchAll(/template:\s*`([\s\S]*?)`\s*,\n/g)].map((m) => m[1]);
}

const attr = (el, name) => el.attributes.find((a) => a.name === name)?.value;
const bound = (el, name) => el.inputs.find((i) => i.name === name)?.value?.source;
// [attr.aria-label] arrives as a bound attribute named aria-label.
const named = (el) => attr(el, 'aria-label') || bound(el, 'aria-label') || attr(el, 'aria-labelledby') || attr(el, 'title');
const hiddenFromAll = (el) => attr(el, 'hidden') !== undefined || attr(el, 'aria-hidden') === 'true';

function kids(node) {
  return [
    ...(node.children ?? []),
    ...(node.branches ?? []),
    ...(node.cases ?? []),
    ...(node.empty ? [node.empty] : []),
    ...(node.placeholder ? [node.placeholder] : []),
    ...(node.loading ? [node.loading] : []),
    ...(node.error ? [node.error] : []),
  ];
}

function hasText(node) {
  if (typeof node.value === 'string' && node.value.trim()) return true; // Text
  if (node.value?.source !== undefined && node.constructor.name.includes('BoundText')) return true;
  if (node.name === 'img' && attr(node, 'alt')) return true;
  // A child component (other than an icon) renders its own text, which a static check can't see.
  if (node.name?.includes('-') && node.name !== 'app-icon') return true;
  if (node.attributes && named(node)) return true;
  return kids(node).some(hasText);
}

function check(source, path) {
  const found = [];
  const parsed = parseTemplate(source, path, { preserveWhitespaces: false });
  if (parsed.errors?.length) return found; // the build reports template errors itself
  const labelsFor = new Set();
  const collect = (node) => {
    if (node.name === 'label') {
      const target = attr(node, 'for') ?? bound(node, 'for');
      if (target) labelsFor.add(target);
    }
    kids(node).forEach(collect);
  };
  parsed.nodes.forEach(collect);
  const visit = (node, inLabel) => {
    if (node.attributes && node.name) {
      const where = `${relative('.', path)} <${node.name}${attr(node, 'id') ? ` id="${attr(node, 'id')}"` : ''}>`;
      if (node.name === 'img' && attr(node, 'alt') === undefined && !bound(node, 'alt')) found.push(`${where}: no alt`);
      if ((node.name === 'button' || node.name === 'a') && !hasText(node)) found.push(`${where}: no name`);
      if (CONTROLS.has(node.name) && !UNLABELLED_INPUTS.has(attr(node, 'type') ?? '') && !hiddenFromAll(node)) {
        const id = attr(node, 'id') ?? bound(node, 'id');
        if (!inLabel && !named(node) && !(id && labelsFor.has(id))) found.push(`${where}: no label`);
      }
      inLabel = inLabel || node.name === 'label';
    }
    kids(node).forEach((child) => visit(child, inLabel));
  };
  parsed.nodes.forEach((node) => visit(node, false));
  return found;
}

// Self-check: a template with one of each mistake must produce exactly three problems; a good one, none.
const bad = check('<input id="a" /><button><app-icon name="x" /></button><img src="x" />', 'self-check.html');
const good = check('<label for="a">A</label><input id="a" /><button [attr.aria-label]="t"><app-icon name="x" /></button><img src="x" alt="" />', 'self-check.html');
if (bad.length !== 3 || good.length !== 0) {
  console.error('The accessibility checker itself is broken:', bad, good);
  process.exit(2);
}

const problems = files(ROOT).flatMap((path) => templates(path).flatMap((source) => check(source, path)));

if (problems.length) {
  console.error(problems.join('\n'));
  console.error(`\n${problems.length} accessibility problem(s).`);
  process.exit(1);
}
console.log('Accessibility check: every image, button, link and form control has a name or label.');
