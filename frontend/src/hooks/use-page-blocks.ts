import { useQuery } from "@tanstack/react-query";
import { fetchPageBlocks } from "@/api/client";
import type { PageBlocksResponse } from "@/api/types";

export function usePageBlocks(route: string) {
  return useQuery<PageBlocksResponse>({
    queryKey: ["page-blocks", route],
    queryFn: () => fetchPageBlocks(route),
  });
}
