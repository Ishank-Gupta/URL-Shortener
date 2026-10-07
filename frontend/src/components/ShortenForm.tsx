import { useState } from "react";
import { shortenUrl, type URLEntry } from "../api";

interface Props {
  onShortened: (entry: URLEntry) => void;
}

export default function ShortenForm({ onShortened }: Props) {
  const [url, setUrl] = useState("");
  const [customAlias, setCustomAlias] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const entry = await shortenUrl(url, customAlias || undefined);
      onShortened(entry);
      setUrl("");
      setCustomAlias("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form className="shorten-form" onSubmit={handleSubmit}>
      <h2>Shorten a URL</h2>
      <div className="form-group">
        <input
          type="url"
          placeholder="https://example.com/very/long/url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          required
          aria-label="URL to shorten"
        />
      </div>
      <div className="form-group">
        <input
          type="text"
          placeholder="Custom alias (optional)"
          value={customAlias}
          onChange={(e) => setCustomAlias(e.target.value)}
          pattern="^[a-zA-Z0-9_-]*$"
          aria-label="Custom alias"
        />
      </div>
      <button type="submit" disabled={loading}>
        {loading ? "Shortening..." : "Shorten"}
      </button>
      {error && <p className="error" role="alert">{error}</p>}
    </form>
  );
}
