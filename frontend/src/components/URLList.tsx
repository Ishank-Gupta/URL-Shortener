import { useState } from "react";
import { deleteUrl, type URLEntry } from "../api";

interface Props {
  urls: URLEntry[];
  onDeleted: (shortCode: string) => void;
}

export default function URLList({ urls, onDeleted }: Props) {
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  const handleCopy = async (shortUrl: string, code: string) => {
    await navigator.clipboard.writeText(shortUrl);
    setCopiedCode(code);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  const handleDelete = async (shortCode: string) => {
    if (!confirm("Delete this short URL?")) return;
    try {
      await deleteUrl(shortCode);
      onDeleted(shortCode);
    } catch {
      alert("Failed to delete URL");
    }
  };

  if (urls.length === 0) {
    return <p className="empty">No URLs shortened yet. Try one above!</p>;
  }

  return (
    <div className="url-list">
      <h2>Your URLs</h2>
      <table>
        <thead>
          <tr>
            <th>Short URL</th>
            <th>Original URL</th>
            <th>Clicks</th>
            <th>Created</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {urls.map((u) => (
            <tr key={u.short_code}>
              <td>
                <a href={u.short_url} target="_blank" rel="noopener noreferrer">
                  {u.short_code}
                </a>
              </td>
              <td className="original-url" title={u.original_url}>
                {u.original_url.length > 50
                  ? u.original_url.slice(0, 50) + "..."
                  : u.original_url}
              </td>
              <td>{u.click_count}</td>
              <td>{new Date(u.created_at).toLocaleDateString()}</td>
              <td className="actions">
                <button
                  onClick={() => handleCopy(u.short_url, u.short_code)}
                  className="btn-copy"
                  aria-label={`Copy short URL for ${u.short_code}`}
                >
                  {copiedCode === u.short_code ? "Copied!" : "Copy"}
                </button>
                <button
                  onClick={() => handleDelete(u.short_code)}
                  className="btn-delete"
                  aria-label={`Delete ${u.short_code}`}
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
