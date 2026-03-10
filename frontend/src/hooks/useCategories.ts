import { useQuery } from '@tanstack/react-query'
import { getCategories } from '../api/categories'

export function useCategories() {
  const { data = [] } = useQuery({
    queryKey: ['categories'],
    queryFn: () => getCategories().then(r => r.data),
    staleTime: 5 * 60 * 1000, // 5 min — categories rarely change
  })

  const categoryNames = data.map(c => c.name)
  const categoryColors: Record<string, string> = Object.fromEntries(data.map(c => [c.name, c.color]))

  return { categories: categoryNames, categoryColors }
}
