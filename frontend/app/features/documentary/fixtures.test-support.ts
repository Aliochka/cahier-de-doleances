import type { HistoricalSearchResult } from "../../lib/api";
export const historical: HistoricalSearchResult = {
  kind: "historical_document",
  corpus_id: "cahiers-1789-ap-stanford",
  document_id: "cahier:Été",
  release_id: "reference-documents-2-7cbcaea79991",
  title: "Cahier d’Aunay-la-Côte",
  source_title: "Cahier d’Avallon",
  place: "Aunay-la-Côte",
  orders: ["tiers état"],
  reference: "Archives parlementaires, tome II, pp. 1–2.",
  sources: [
    { label: "Notice Persée", url: "https://www.persee.fr/doc/source" },
  ],
  warnings: [
    { code: "lacuna", message: "Le début de la transcription manque." },
  ],
  url: "/parcourir/1789/reference-documents-2-7cbcaea79991/documents/cahier%3A%C3%89t%C3%A9?unit=passage%3A1#passage-passage%3A1",
  rank: 1,
  excerpt: "Été 😀\n\n<script>sans HTML</script>",
  unit_id: "passage:1",
  start_offset: 4,
  end_offset: 42,
  match_origin: "text",
};
