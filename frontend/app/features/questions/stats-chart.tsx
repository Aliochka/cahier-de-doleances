import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { token } from "../../../styled-system/tokens";
import type { QuestionStatistics } from "../../lib/api";

/** Loaded only after hydration; the complete HTML table remains the primary alternative. */
export default function QuestionStatsChart({
  stats,
}: {
  stats: QuestionStatistics;
}) {
  return (
    <ResponsiveContainer
      width="100%"
      height={stats.categories.length * 48 + 64}
      minWidth={0}
    >
      <BarChart data={stats.categories} layout="vertical" accessibilityLayer>
        <XAxis
          type="number"
          allowDecimals={false}
          stroke={token("colors.text")}
        />
        <YAxis
          type="category"
          dataKey="label"
          width={36}
          tickFormatter={(_label, index) => String(index + 1)}
          stroke={token("colors.text")}
        />
        <Tooltip
          content={({ active, activeIndex }) => {
            if (!active || activeIndex === undefined) return null;
            const category = stats.categories.find(
              (_category, index) => String(index) === String(activeIndex),
            );
            return category ? (
              <div
                style={{
                  background: token("colors.surface"),
                  border: `1px solid ${token("colors.border")}`,
                  color: token("colors.text"),
                  padding: 8,
                  maxWidth: 160,
                  overflowWrap: "anywhere",
                }}
              >
                {category.label} : {category.count} sélections (
                {category.percentage} %)
              </div>
            ) : null;
          }}
        />
        <Bar
          dataKey="count"
          name="Sélections"
          fill={token("colors.primary")}
          isAnimationActive={false}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
