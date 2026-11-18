import test from 'node:test';
import assert from 'node:assert/strict';
import {
  DEFAULT_MODS,
  parseModMetadata,
  validatePythonLikeSyntax,
  mergeStoredMods,
  filterModsList,
  sanitizeModFilename,
} from '../web_mod_editor.mjs';

test('DEFAULT_MODS includes all 5 game & community mods with valid syntax', () => {
  assert.equal(DEFAULT_MODS.length, 5);
  for (const mod of DEFAULT_MODS) {
    const check = validatePythonLikeSyntax(mod.code);
    assert.equal(check.valid, true, `Syntax errors in ${mod.filename}: ${check.errors.join('; ')}`);
    assert.ok(check.hooks.length >= 1, `Expected at least one hook in ${mod.filename}`);
  }
});

test('parseModMetadata extracts MOD_NAME/MOD_DESC and MOD_META fields', () => {
  const simple = `MOD_NAME = "Shadow Blade"\nMOD_DESC = "Adds +2 damage"\n`;
  assert.deepEqual(parseModMetadata(simple, 'fallback.py'), {
    title: 'Shadow Blade',
    desc: 'Adds +2 damage',
  });

  const dictMeta = `MOD_META = {\n  "name": "Пак Бездны",\n  "description": "Описание пака",\n}\n`;
  assert.deepEqual(parseModMetadata(dictMeta, 'abyss.py'), {
    title: 'Пак Бездны',
    desc: 'Описание пака',
  });
});

test('validatePythonLikeSyntax detects unclosed brackets, quotes, and DarkVault hooks', () => {
  const good = validatePythonLikeSyntax(
    'def on_register(api):\n    api.add_item({"id": "x"})\n\ndef on_room_enter(api, g, r, p):\n    pass\n'
  );
  assert.equal(good.valid, true);
  assert.deepEqual(good.hooks, ['on_register', 'on_room_enter']);

  const badBracket = validatePythonLikeSyntax('def on_register(api:\n    pass\n');
  assert.equal(badBracket.valid, false);
  assert.ok(badBracket.errors.some((e) => e.includes('незакрытая') || e.includes('лишняя')));

  const badQuote = validatePythonLikeSyntax('MOD_NAME = "unclosed\n');
  assert.equal(badQuote.valid, false);
  assert.ok(badQuote.errors.some((e) => e.includes('кавычка')));

  const empty = validatePythonLikeSyntax('   ');
  assert.equal(empty.valid, false);
});

test('mergeStoredMods keeps user edits and seeds newly added community mods', () => {
  const legacySaved = [
    {
      filename: 'quick_boost_example.py',
      title: 'Quick Boost Edited',
      desc: 'Custom desc',
      enabled: false,
      code: 'MOD_NAME = "Quick Boost Edited"\nMOD_DESC = "Custom desc"\ndef on_register(api): pass\n',
    },
    {
      filename: 'my_custom.py',
      title: 'My Mod',
      desc: 'Desc',
      enabled: true,
      code: 'def on_run_start(api, g, p): pass\n',
    },
  ];
  const merged = mergeStoredMods(legacySaved, DEFAULT_MODS);
  assert.equal(merged.length, 6);
  assert.equal(merged[0].enabled, false);
  assert.equal(merged[0].title, 'Quick Boost Edited');
  assert.ok(merged.some((m) => m.filename === 'abyss_vortex_pack.py'));
  assert.ok(merged.some((m) => m.filename === 'my_custom.py'));
});

test('filterModsList and sanitizeModFilename behave deterministically', () => {
  const filtered = filterModsList(DEFAULT_MODS, 'Vortex');
  assert.equal(filtered.length, 1);
  assert.equal(filtered[0].filename, 'abyss_vortex_pack.py');

  assert.equal(sanitizeModFilename('My Cool Mod!', ['my_cool_mod.py']), 'my_cool_mod_2.py');
  assert.equal(sanitizeModFilename('   ', []), 'custom_mod.py');
});

test('index.html, metadata.json, and LICENSE are valid and consistent', async () => {
  const fs = await import('node:fs');
  const html = fs.readFileSync(new URL('../index.html', import.meta.url), 'utf8');
  assert.ok(html.includes('web_mod_editor.mjs'), 'index.html should import web_mod_editor.mjs');
  assert.ok(html.includes('<title>') && html.includes('</title>'), 'index.html should contain a title');
  assert.ok(html.includes('</html>'), 'index.html should close html tag');

  const meta = JSON.parse(fs.readFileSync(new URL('../metadata.json', import.meta.url), 'utf8'));
  assert.ok(typeof meta.name === 'string' && meta.name.length > 0);
  assert.ok(typeof meta.description === 'string' && meta.description.length > 0);

  const license = fs.readFileSync(new URL('../LICENSE', import.meta.url), 'utf8');
  assert.ok(license.includes('Maksim Polienko'), 'LICENSE should preserve copyright holder');
});

