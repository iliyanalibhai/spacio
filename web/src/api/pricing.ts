import api from "./client";

export async function suggestPrice(input: {
  size: "S" | "M" | "L";
  zipCode: string;
  indoor?: boolean;
  sizeSqft?: number;
  title?: string;
  description?: string;
}) {
  const { data } = await api.post<{
    suggestedPrice: number;
    minPrice: number;
    maxPrice: number;
    explanation: string;
  }>("/pricing/suggest", input);
  return data;
}
