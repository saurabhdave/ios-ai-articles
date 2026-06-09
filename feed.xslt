<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:atom="http://www.w3.org/2005/Atom">

  <xsl:output method="html" version="5.0" encoding="UTF-8" indent="yes"/>

  <xsl:template match="/">
    <html lang="en">
      <head>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1"/>
        <title><xsl:value-of select="atom:feed/atom:title"/> — RSS Feed</title>
        <link rel="stylesheet" href="assets/css/fonts.css"/>
        <style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
a { color: inherit; text-decoration: none; }

:root {
  --paper:    #ece9e2;
  --paper-2:  #e4e0d7;
  --ink:      #16130d;
  --muted:    #6c6557;
  --hair:     rgba(22,19,13,0.14);
  --accent:   #f05138;
  --row-hover:rgba(22,19,13,0.035);
  --font:     'Geist', 'Helvetica Neue', Arial, sans-serif;
  --font-d:   'Geist', 'Helvetica Neue', Arial, sans-serif;
  --font-read:'Source Serif 4', Georgia, 'Times New Roman', serif;
  --mono:     ui-monospace, 'SF Mono', 'JetBrains Mono', Menlo, monospace;
  --radius:   12px;
  --max-w:    760px;
}

@media (prefers-color-scheme: dark) {
  :root {
    --paper:    #15130e;
    --paper-2:  #211d16;
    --ink:      #ece7db;
    --muted:    #9d9582;
    --hair:     rgba(236,231,219,0.14);
    --accent:   #ff6a4d;
    --row-hover:rgba(236,231,219,0.05);
  }
}

body {
  background: var(--paper);
  color: var(--ink);
  font-family: var(--font);
  font-size: 15px;
  line-height: 1.6;
  min-height: 100vh;
  padding: 0 20px 80px;
  -webkit-font-smoothing: antialiased;
}

.wrap { max-width: var(--max-w); margin: 0 auto; }

/* ── Header ── */
.feed-header {
  padding: 64px 0 44px;
  border-bottom: 1px solid var(--hair);
  margin-bottom: 40px;
}

.feed-badge {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: var(--accent);
  font-family: var(--mono);
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  margin-bottom: 18px;
}

.feed-badge svg { flex-shrink: 0; }

.feed-title {
  font-family: var(--font-d);
  font-size: clamp(30px, 5vw, 48px);
  font-weight: 500;
  letter-spacing: -0.02em;
  line-height: 1.05;
  margin-bottom: 14px;
  color: var(--ink);
}

.feed-desc {
  color: var(--muted);
  font-size: 17px;
  line-height: 1.5;
  margin-bottom: 30px;
  max-width: 560px;
}

/* ── Subscribe box ── */
.subscribe-box {
  background: var(--paper-2);
  border: 1px solid var(--hair);
  border-radius: var(--radius);
  padding: 22px 24px;
}

.subscribe-label {
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 12px;
}

.feed-url-row {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 16px;
}

.feed-url {
  flex: 1;
  min-width: 0;
  font-family: var(--mono);
  font-size: 12.5px;
  color: var(--accent);
  background: var(--paper);
  border: 1px solid var(--hair);
  border-radius: 8px;
  padding: 9px 12px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  display: block;
}

.copy-btn {
  background: var(--ink);
  color: var(--paper);
  border: none;
  border-radius: 999px;
  font-family: var(--font);
  font-size: 13px;
  font-weight: 500;
  padding: 9px 18px;
  cursor: pointer;
  white-space: nowrap;
  transition: opacity 0.15s;
  flex-shrink: 0;
}

.copy-btn:hover { opacity: 0.88; }
.copy-btn.copied { background: var(--accent); }

.reader-links {
  font-size: 13.5px;
  color: var(--muted);
}

.reader-links a {
  color: var(--ink);
  text-decoration: underline;
  text-underline-offset: 3px;
  transition: color 0.15s;
}

.reader-links a:hover { color: var(--accent); }

/* ── Entries ── */
.entries { display: flex; flex-direction: column; }

.entry {
  display: block;
  padding: 24px 0;
  border-bottom: 1px solid var(--hair);
  transition: background 0.18s;
}

.entry:hover { background: var(--row-hover); }

.entry-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 9px;
  flex-wrap: wrap;
}

.entry-date {
  font-family: var(--mono);
  font-size: 12px;
  color: var(--muted);
  font-variant-numeric: tabular-nums;
}

.tag {
  font-family: var(--mono);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--accent);
}

.entry-title {
  font-family: var(--font-d);
  font-size: 22px;
  font-weight: 500;
  letter-spacing: -0.01em;
  line-height: 1.2;
  margin-bottom: 10px;
}

.entry-title a {
  color: var(--ink);
  transition: color 0.15s;
}

.entry-title a:hover { color: var(--accent); }

.entry-summary {
  font-family: var(--font-read);
  font-size: 16px;
  color: var(--muted);
  line-height: 1.55;
  margin-bottom: 14px;
  max-width: 64ch;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.read-more {
  font-family: var(--mono);
  font-size: 13px;
  color: var(--ink);
  text-decoration: underline;
  text-underline-offset: 3px;
  transition: color 0.15s;
}

.read-more:hover { color: var(--accent); }

/* ── Footer ── */
.feed-footer {
  margin-top: 48px;
  padding-top: 24px;
  border-top: 1px solid var(--hair);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}

.feed-footer p {
  font-family: var(--mono);
  font-size: 12px;
  color: var(--muted);
}

.back-link {
  font-family: var(--mono);
  font-size: 13px;
  color: var(--ink);
  text-decoration: underline;
  text-underline-offset: 3px;
  transition: color 0.15s;
}

.back-link:hover { color: var(--accent); }
        </style>
      </head>
      <body>
        <div class="wrap">

          <!-- Header -->
          <header class="feed-header">
            <div class="feed-badge">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <circle cx="6.18" cy="17.82" r="2.18"/>
                <path d="M4 4.44v2.83c7.03 0 12.73 5.7 12.73 12.73h2.83c0-8.59-6.97-15.56-15.56-15.56zm0 5.66v2.83c3.9 0 7.07 3.17 7.07 7.07h2.83c0-5.47-4.43-9.9-9.9-9.9z"/>
              </svg>
              RSS Feed
            </div>

            <h1 class="feed-title">
              <xsl:value-of select="atom:feed/atom:title"/>
            </h1>
            <p class="feed-desc">
              <xsl:value-of select="atom:feed/atom:subtitle"/>
            </p>

            <div class="subscribe-box">
              <p class="subscribe-label">Subscribe — paste this URL into your RSS reader</p>
              <div class="feed-url-row">
                <code class="feed-url" id="feed-url">
                  <xsl:value-of select="atom:feed/atom:link[@rel='self']/@href"/>
                </code>
                <button class="copy-btn" id="copy-btn" onclick="copyFeedUrl()">Copy</button>
              </div>
              <p class="reader-links">
                Open in:&#160;
                <a href="https://feedly.com/i/subscription/feed/https%3A%2F%2Fsaurabhdave.github.io%2Fios-ai-articles%2Ffeed.xml">Feedly</a>
                &#160;·&#160;
                <a href="https://www.inoreader.com/?add_feed=https://saurabhdave.github.io/ios-ai-articles/feed.xml">Inoreader</a>
                &#160;·&#160;
                <a href="https://reederapp.com">Reeder</a>
                &#160;·&#160;
                <a href="https://netnewswire.com">NetNewsWire</a>
              </p>
            </div>
          </header>

          <!-- Entry list -->
          <section class="entries">
            <xsl:for-each select="atom:feed/atom:entry">
              <article class="entry">
                <div class="entry-meta">
                  <time class="entry-date">
                    <xsl:value-of select="substring(atom:published, 1, 10)"/>
                  </time>
                  <xsl:for-each select="atom:category">
                    <span class="tag"><xsl:value-of select="@term"/></span>
                  </xsl:for-each>
                </div>
                <h2 class="entry-title">
                  <a href="{atom:link[@rel='alternate']/@href}">
                    <xsl:value-of select="atom:title"/>
                  </a>
                </h2>
                <p class="entry-summary">
                  <xsl:call-template name="strip-tags">
                    <xsl:with-param name="text" select="atom:summary"/>
                  </xsl:call-template>
                </p>
                <a class="read-more" href="{atom:link[@rel='alternate']/@href}">
                  Read article &#x2192;
                </a>
              </article>
            </xsl:for-each>
          </section>

          <!-- Footer -->
          <footer class="feed-footer">
            <p>
              <xsl:value-of select="count(atom:feed/atom:entry)"/> articles ·
              Atom/RSS feed
            </p>
            <a class="back-link" href="{atom:feed/atom:link[@rel='alternate']/@href}">
              &#x2190; Back to blog
            </a>
          </footer>

        </div>

        <script>
function copyFeedUrl() {
  var url = document.getElementById('feed-url').textContent.trim();
  navigator.clipboard.writeText(url).then(function() {
    var btn = document.getElementById('copy-btn');
    btn.textContent = 'Copied!';
    btn.classList.add('copied');
    setTimeout(function() {
      btn.textContent = 'Copy';
      btn.classList.remove('copied');
    }, 2000);
  });
}
        </script>
      </body>
    </html>
  </xsl:template>

  <!-- Strip HTML tags from a string (Atom summaries carry escaped markup).
       Pure XSLT 1.0 string ops so it works in every browser's XSLT engine. -->
  <xsl:template name="strip-tags">
    <xsl:param name="text"/>
    <xsl:choose>
      <xsl:when test="contains($text, '&lt;')">
        <xsl:value-of select="substring-before($text, '&lt;')"/>
        <xsl:call-template name="strip-tags">
          <xsl:with-param name="text" select="substring-after($text, '&gt;')"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise>
        <xsl:value-of select="$text"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

</xsl:stylesheet>
