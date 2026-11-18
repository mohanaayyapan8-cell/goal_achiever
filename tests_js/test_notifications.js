// Tests static/js/notifications.js with a stubbed browser (no real browser needed).
const fs = require("fs"), path = require("path"), assert = require("assert");
const source = fs.readFileSync(path.resolve(__dirname, "../static/js/notifications.js"), "utf8");
const tick = () => new Promise(r => setImmediate(r));
async function flush() { for (let i = 0; i < 5; i++) await tick(); }

async function run({ pollUrl = "/poll/", flag = "1", permission = "granted", responses, stored = "[]", storageBroken = false, notificationBroken = false }) {
  const popups = [], timers = [], store = { v: stored };
  const bell = { textContent: "", hidden: true };
  global.document = { body: { dataset: { pollUrl: pollUrl || undefined, browserNotify: flag } }, getElementById: id => id === "bell-count" ? bell : null };
  global.localStorage = storageBroken ? { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); } }
                                      : { getItem: () => store.v, setItem: (k, v) => { store.v = v; } };
  global.Notification = function (title, opts) { if (notificationBroken) throw new Error("blocked"); this.title = title; this.opts = opts; popups.push(this); };
  global.Notification.permission = permission;
  global.window = { Notification: global.Notification, focus() {}, location: { href: "/here/" } };
  global.setInterval = (fn) => { timers.push(fn); return 1; };
  let call = 0;
  global.fetch = async () => {
    const r = responses[Math.min(call++, responses.length - 1)];
    if (r === "fail") throw new Error("offline");
    return { ok: r.ok !== false, json: async () => r };
  };
  new Function(source)();
  await flush();
  return { popups, bell, timers, store, again: async () => { timers[0](); await flush(); } };
}

const item = (id, extra) => Object.assign({ id, kind: "reminder", title: "T" + id, message: "M" + id, link: "/planner/today/" }, extra);

(async () => {
  // 1) enabled + granted: pop-ups for new items, never twice, bell updated, click opens the link
  let t = await run({ responses: [{ unread: 2, items: [item(1), item(2)] }, { unread: 3, items: [item(1), item(2), item(3)] }] });
  assert.strictEqual(t.popups.length, 2);
  assert.strictEqual(t.popups[0].title, "T1"); assert.strictEqual(t.popups[0].opts.body, "M1"); assert.strictEqual(t.popups[0].opts.tag, "ga-1");
  assert.strictEqual(t.bell.textContent, 2); assert.strictEqual(t.bell.hidden, false);
  await t.again();
  assert.strictEqual(t.popups.length, 3, "only the new item should pop up");
  assert.strictEqual(t.bell.textContent, 3);
  t.popups[2].onclick(); assert.strictEqual(window.location.href, "/planner/today/");
  assert.strictEqual(t.timers.length, 1, "polls on a timer");
  assert.deepStrictEqual(JSON.parse(t.store.v), [1, 2, 3]);

  // 2) items remembered from an earlier page are not shown again
  t = await run({ stored: "[1]", responses: [{ unread: 1, items: [item(1)] }] });
  assert.strictEqual(t.popups.length, 0);

  // 3) user did not enable browser notifications: bell updates, no pop-ups
  t = await run({ flag: "0", responses: [{ unread: 4, items: [item(9)] }] });
  assert.strictEqual(t.popups.length, 0); assert.strictEqual(t.bell.textContent, 4);

  // 4) browser permission not granted: no pop-ups
  for (const permission of ["denied", "default"]) {
    t = await run({ permission, responses: [{ unread: 1, items: [item(5)] }] });
    assert.strictEqual(t.popups.length, 0, permission); assert.strictEqual(t.bell.textContent, 1);
  }

  // 5) zero unread hides the bell badge
  t = await run({ responses: [{ unread: 0, items: [] }] });
  assert.strictEqual(t.bell.hidden, true);

  // 6) network failure or server error is harmless and the timer still runs
  t = await run({ responses: ["fail"] }); assert.strictEqual(t.popups.length, 0); assert.strictEqual(t.timers.length, 1);
  t = await run({ responses: [{ ok: false }] }); assert.strictEqual(t.popups.length, 0);

  // 7) anonymous pages (no poll url): the script does nothing
  t = await run({ pollUrl: "", responses: [{ unread: 1, items: [item(1)] }] });
  assert.strictEqual(t.popups.length, 0); assert.strictEqual(t.timers.length, 0);

  // 8) storage blocked or Notification constructor blocked: still no crash
  t = await run({ storageBroken: true, responses: [{ unread: 1, items: [item(1)] }] }); assert.strictEqual(t.popups.length, 1);
  t = await run({ notificationBroken: true, responses: [{ unread: 1, items: [item(1)] }] }); assert.strictEqual(t.bell.textContent, 1);

  console.log("notifications.js stub test: all assertions passed");
})().catch(e => { console.error("FAILED:", e.message); process.exit(1); });
