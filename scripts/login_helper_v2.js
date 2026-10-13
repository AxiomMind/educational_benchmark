const { chromium } = require('playwright');
const fs = require('fs');

const COOKIE_PATH = 'C:/Users/26730/educational_benchmark/data/xkw_cookies.json';

(async () => {
  console.log('>>> 正在启动可视化浏览器登录窗口，窗口将保持打开至少 10 分钟...');
  const browser = await chromium.launch({
    headless: false,
    args: [
      '--start-maximized',
      '--disable-blink-features=AutomationControlled'
    ]
  });

  const context = await browser.newContext({
    viewport: { width: 1280, height: 850 },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
  });

  const page = await context.newPage();
  console.log('>>> 正在打开组卷网首页...');

  try {
    await page.goto('https://zujuan.xkw.com/gzls/', { waitUntil: 'domcontentloaded', timeout: 45000 });
  } catch (err) {
    console.log('页面加载提示:', err.message);
  }

  await page.waitForTimeout(3000);

  // 尝试自动触发登录弹窗
  console.log('>>> 正在自动唤起微信扫码登录弹窗...');
  try {
    await page.evaluate(() => {
      if (typeof logindiv === 'function') {
        logindiv();
      } else {
        const btn = document.querySelector('.login-btn');
        if (btn) btn.click();
      }
    });
    console.log('>>> 登录弹窗已唤起！');
  } catch (e) {
    console.log('唤起登录弹窗提示:', e.message);
  }

  // 在页面顶部注入一个醒目的操作提示栏
  await page.evaluate(() => {
    const tip = document.createElement('div');
    tip.id = 'hermes-login-banner';
    tip.style.position = 'fixed';
    tip.style.top = '0';
    tip.style.left = '0';
    tip.style.width = '100%';
    tip.style.backgroundColor = '#1890ff';
    tip.style.color = '#ffffff';
    tip.style.fontSize = '16px';
    tip.style.fontWeight = 'bold';
    tip.style.textAlign = 'center';
    tip.style.padding = '12px 0';
    tip.style.zIndex = '999999';
    tip.style.boxShadow = '0 2px 8px rgba(0,0,0,0.3)';
    tip.innerText = '👉 请在下方弹窗中扫码登录您刚刚充值了会员的组卷网账号。登录成功后本窗口将自动识别并保存！';
    document.body.prepend(tip);
  }).catch(() => {});

  console.log('\n================================================================');
  console.log(' 请在弹出的浏览器窗口中扫码或输入验证码登录 VIP 账号！');
  console.log(' 本窗口设有 10 分钟充足等待时间，请从容扫码。');
  console.log(' 脚本只有在确认您扫码成功进入个人中心后，才会保存 Cookie 并退出。');
  console.log('================================================================\n');

  const startTime = Date.now();
  let loggedIn = false;

  // 最多等待 10 分钟 (600,000 ms)
  while (Date.now() - startTime < 600000) {
    await page.waitForTimeout(3000);

    const cookies = await context.cookies();
    const cookieNames = cookies.map(c => c.name.toLowerCase());

    // 严谨判断：必须包含真实登录令牌 user_token 或 userId
    const hasRealToken = cookieNames.includes('user_token') || cookieNames.includes('userid');

    const userInfo = await page.evaluate(() => {
      // 检查个人中心盒子
      const userBox = document.querySelector('.user-info-box, .user-info-base, .item.user-info');
      const logoutBtn = document.querySelector('a[href*="logout"], a:has-text("退出")');
      const loginBtn = document.querySelector('a.login-btn');
      
      const isLoginBtnGone = !loginBtn || loginBtn.offsetParent === null;
      
      if (userBox && (logoutBtn || isLoginBtnGone)) {
        return userBox.innerText.replace(/\s+/g, ' ');
      }
      return null;
    }).catch(() => null);

    if (hasRealToken && userInfo && !userInfo.includes('登录 注册')) {
      console.log('>>> 🎉 确认登录成功！');
      console.log('>>> 当前账号信息:', userInfo);

      // 更新顶部横幅提示用户
      await page.evaluate((info) => {
        const tip = document.getElementById('hermes-login-banner');
        if (tip) {
          tip.style.backgroundColor = '#52c41a';
          tip.innerText = '✅ 登录成功！正在保存 VIP 凭证并在 5 秒后自动关闭...';
        }
      }, userInfo).catch(() => {});

      // 稍微等待 5 秒，确保所有 VIP 相关的 Cookie 刷新齐全
      await page.waitForTimeout(5000);
      const freshCookies = await context.cookies();
      fs.writeFileSync(COOKIE_PATH, JSON.stringify(freshCookies, null, 2), 'utf8');
      console.log('>>> 🎉 最新 VIP Cookie 已成功保存到:', COOKIE_PATH);
      loggedIn = true;
      break;
    }
  }

  if (!loggedIn) {
    console.log('>>> 扫码登录等待超时（10分钟）。');
  }

  await page.waitForTimeout(2000);
  await browser.close();
  process.exit(loggedIn ? 0 : 1);
})();
