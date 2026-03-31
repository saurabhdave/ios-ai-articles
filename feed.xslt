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
        <link rel="preconnect" href="https://fonts.googleapis.com"/>
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous"/>
        <link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600&amp;family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,400;1,9..144,300&amp;display=swap" rel="stylesheet"/>
        <style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
a { color: inherit; text-decoration: none; }

:root {
  --bg:           #08090d;
  --bg-card:      #0e1019;
  --bg-card-h:    #131621;
  --border:       rgba(255,255,255,0.055);
  --border-mid:   rgba(255,255,255,0.10);
  --border-h:     rgba(240,184,64,0.36);
  --text-1:       #f0ece5;
  --text-2:       #7c8099;
  --accent:       #f0b840;
  --accent-soft:  rgba(240,184,64,0.08);
  --accent-dim:   rgba(240,184,64,0.55);
  --accent-glow:  rgba(240,184,64,0.16);
  --font:         'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-d:       'Fraunces', Georgia, serif;
  --mono:         'JetBrains Mono', 'SF Mono', monospace;
  --radius:       10px;
  --max-w:        720px;
}

body {
  background: var(--bg);
  color: var(--text-1);
  font-family: var(--font);
  font-size: 15px;
  line-height: 1.6;
  min-height: 100vh;
  padding: 0 16px 80px;
}

.wrap { max-width: var(--max-w); margin: 0 auto; }

/* ── Header ── */
.feed-header {
  padding: 56px 0 48px;
  border-bottom: 1px solid var(--border-mid);
  margin-bottom: 40px;
}

.feed-badge {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  background: var(--accent-soft);
  border: 1px solid rgba(240,184,64,0.22);
  color: var(--accent);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  padding: 4px 12px 4px 9px;
  border-radius: 100px;
  margin-bottom: 20px;
}

.feed-badge svg { flex-shrink: 0; }

.feed-title {
  font-family: var(--font-d);
  font-size: clamp(26px, 5vw, 36px);
  font-weight: 400;
  line-height: 1.2;
  margin-bottom: 10px;
  color: var(--text-1);
}

.feed-desc {
  color: var(--text-2);
  font-size: 15px;
  margin-bottom: 28px;
  max-width: 560px;
}

/* ── Subscribe box ── */
.subscribe-box {
  background: var(--bg-card);
  border: 1px solid var(--border-mid);
  border-radius: var(--radius);
  padding: 20px 22px;
}

.subscribe-label {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--text-2);
  margin-bottom: 10px;
}

.feed-url-row {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 14px;
}

.feed-url {
  flex: 1;
  font-family: var(--mono);
  font-size: 12.5px;
  color: var(--accent);
  background: rgba(240,184,64,0.05);
  border: 1px solid rgba(240,184,64,0.15);
  border-radius: 6px;
  padding: 7px 12px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  display: block;
}

.copy-btn {
  background: var(--accent);
  color: #08090d;
  border: none;
  border-radius: 6px;
  font-family: var(--font);
  font-size: 12.5px;
  font-weight: 600;
  padding: 7px 16px;
  cursor: pointer;
  white-space: nowrap;
  transition: opacity 0.15s, background 0.15s;
  flex-shrink: 0;
}

.copy-btn:hover { opacity: 0.88; }
.copy-btn.copied { background: #38c2b8; }

.reader-links {
  font-size: 13px;
  color: var(--text-2);
}

.reader-links a {
  color: var(--accent-dim);
  border-bottom: 1px solid transparent;
  transition: color 0.15s, border-color 0.15s;
}

.reader-links a:hover {
  color: var(--accent);
  border-bottom-color: var(--accent-dim);
}

/* ── Entries ── */
.entries { display: flex; flex-direction: column; gap: 2px; }

.entry {
  padding: 24px 22px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  transition: background 0.18s, border-color 0.18s, box-shadow 0.18s;
}

.entry:hover {
  background: var(--bg-card-h);
  border-color: var(--border-h);
  box-shadow: 0 0 0 1px rgba(240,184,64,0.06), 0 8px 32px rgba(0,0,0,0.4);
}

.entry-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.entry-date {
  font-size: 12px;
  color: var(--text-2);
  font-variant-numeric: tabular-nums;
}

.tag {
  font-size: 11px;
  font-weight: 500;
  color: var(--accent-dim);
  background: var(--accent-soft);
  border: 1px solid rgba(240,184,64,0.14);
  padding: 2px 8px;
  border-radius: 100px;
  letter-spacing: 0.03em;
}

.entry-title {
  font-family: var(--font-d);
  font-size: 19px;
  font-weight: 400;
  line-height: 1.35;
  margin-bottom: 8px;
}

.entry-title a {
  color: var(--text-1);
  transition: color 0.15s;
}

.entry-title a:hover { color: var(--accent); }

.entry-summary {
  font-size: 13.5px;
  color: var(--text-2);
  line-height: 1.65;
  margin-bottom: 14px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.read-more {
  font-size: 12.5px;
  font-weight: 500;
  color: var(--accent);
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border-bottom: 1px solid transparent;
  transition: border-color 0.15s, gap 0.15s;
}

.read-more:hover {
  border-bottom-color: var(--accent-dim);
  gap: 7px;
}

/* ── Footer ── */
.feed-footer {
  margin-top: 56px;
  padding-top: 24px;
  border-top: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}

.feed-footer p {
  font-size: 12.5px;
  color: var(--text-2);
}

.back-link {
  font-size: 12.5px;
  font-weight: 500;
  color: var(--accent-dim);
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border-bottom: 1px solid transparent;
  transition: color 0.15s, border-color 0.15s;
}

.back-link:hover { color: var(--accent); border-bottom-color: var(--accent-dim); }
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
                  <xsl:value-of select="atom:summary"/>
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

</xsl:stylesheet>
