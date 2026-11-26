/* Browser-side search over Nathe's automatically published static index. */
window.NatheResearch = (() => {
    const state = { ready: false, error: null, generatedAt: null, pages: [] };
    const STOP_WORDS = new Set([
        "a", "about", "after", "again", "all", "also", "an", "and", "any", "are",
        "as", "at", "be", "because", "been", "before", "being", "but", "by",
        "can", "could", "did", "do", "does", "for", "from", "had", "has", "have",
        "how", "i", "if", "in", "into", "is", "it", "its", "may", "more", "most",
        "not", "of", "on", "or", "our", "out", "should", "so", "such", "than",
        "that", "the", "their", "them", "then", "there", "these", "they", "this",
        "those", "to", "too", "was", "we", "were", "what", "when", "where", "which",
        "who", "why", "will", "with", "would", "you", "your"
    ]);

    function terms(value) {
        return (String(value || "").toLowerCase().match(/[a-z0-9]{2,}/g) || [])
            .filter(term => !STOP_WORDS.has(term));
    }

    function excerptFor(page, queryTerms) {
        const paragraphs = String(page.text || page.snippet || "")
            .split(/\n+/).map(value => value.trim()).filter(Boolean);
        if (!paragraphs.length) return String(page.snippet || "").slice(0, 300);
        let best = paragraphs[0];
        let bestScore = -1;
        for (const paragraph of paragraphs) {
            const lower = paragraph.toLowerCase();
            const score = queryTerms.reduce((total, term) => {
                return total + Math.max(0, lower.split(term).length - 1);
            }, 0);
            if (score > bestScore) {
                best = paragraph;
                bestScore = score;
            }
        }
        return best.length > 360 ? best.slice(0, 357).replace(/\s+\S*$/, "") + "…" : best;
    }

    const ready = fetch(new URL("research-index.json", document.baseURI), {
        credentials: "same-origin",
        cache: "no-store"
    }).then(response => {
        if (!response.ok) throw new Error("HTTP " + response.status);
        return response.json();
    }).then(data => {
        if (!data || data.version !== 1 || !Array.isArray(data.pages)) {
            throw new Error("The published research index has an invalid format.");
        }
        state.pages = data.pages.filter(page =>
            page && typeof page.url === "string"
            && page.url.startsWith("https://")
            && typeof page.title === "string"
            && typeof page.text === "string"
        );
        state.generatedAt = data.generated_at || null;
        state.ready = true;
        return state;
    }).catch(error => {
        state.error = error;
        throw error;
    });

    function search(query, limit = 3) {
        if (!state.ready) return [];
        const queryTerms = [...new Set(terms(query))];
        if (!queryTerms.length) return [];
        const phrase = queryTerms.join(" ");
        const ranked = [];

        for (const page of state.pages) {
            const title = page.title.toLowerCase();
            const text = page.text.toLowerCase();
            let score = 0;
            for (const term of queryTerms) {
                score += Math.min(title.split(term).length - 1, 4) * 5;
                score += Math.min(text.split(term).length - 1, 10) * 1.1;
            }
            if (title.includes(phrase)) score += 10;
            else if (text.includes(phrase)) score += 3;
            if (score <= 0) continue;
            ranked.push({
                url: page.url,
                host: page.host || "",
                title: page.title,
                excerpt: excerptFor(page, queryTerms),
                published_at: page.published_at || "",
                fetched_at: page.fetched_at || "",
                score
            });
        }
        ranked.sort((left, right) => right.score - left.score);
        return ranked.slice(0, Math.max(1, Math.min(5, limit)));
    }

    function status() {
        return {
            ready: state.ready,
            error: state.error ? state.error.message : null,
            pageCount: state.pages.length,
            generatedAt: state.generatedAt
        };
    }

    return { ready, search, status };
})();
