export function createTools({ root }) {
  root.innerHTML = `<section class="report-workspace tools-workspace">
    <header class="report-page-head"><div><div class="eyebrow">Tools · Reviews</div><h1>Tools</h1><p>Manage scheduled reviews.</p></div></header>
    <section class="card settings-section"><h2>定期审查邮件</h2><p>手动触发每周审查，查看 Jira、Confluence 报告及逐次历史。</p><a class="button button-primary" href="/audit-email.html">管理审查报告</a></section>
  </section>`
  return {
    async start() {},
    destroy() {},
  }
}
