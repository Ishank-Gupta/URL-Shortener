import { useEffect, useState } from "react";
import ShortenForm from "./components/ShortenForm";
import URLList from "./components/URLList";
import { listUrls, type URLEntry } from "./api";

export default function App() {
  const [urls, setUrls] = useState<URLEntry[]>([]);

  const fetchUrls = async () => {
    try {
      const data = await listUrls();
      setUrls(data);
    } catch {
      console.error("Failed to load URLs");
    }
  };

  useEffect(() => {
    fetchUrls();
  }, []);

  const handleShortened = (entry: URLEntry) => {
    setUrls((prev) => {
      // Duplicate detection returns the existing entry — replace it if present
      const existing = prev.findIndex((u) => u.short_code === entry.short_code);
      if (existing >= 0) {
        const updated = [...prev];
        updated[existing] = entry;
        return updated;
      }
      return [entry, ...prev];
    });
  };

  const handleDeleted = (shortCode: string) => {
    setUrls((prev) => prev.filter((u) => u.short_code !== shortCode));
  };

  return (
    <div className="container">
      <header>
        <h1>🔗 URL Shortener</h1>
        <p>Shorten your links, track your clicks</p>
      </header>
      <main>
        <ShortenForm onShortened={handleShortened} />
        <URLList urls={urls} onDeleted={handleDeleted} />
      </main>
    </div>
  );
}
