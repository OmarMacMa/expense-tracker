import { useMembers } from './useMembers';
import { useCategories } from './useCategories';
import { useTags } from './useTags';
import { usePaymentMethods } from './usePaymentMethods';
import { useMerchantList } from './useMerchants';

export function useExpenseFilterOptions() {
  const members = useMembers();
  const categories = useCategories();
  const tags = useTags();
  const methods = usePaymentMethods();
  const merchants = useMerchantList();
  return {
    spenders: members.data,
    categories: categories.data,
    tags: tags.data,
    paymentMethods: methods.data,
    merchants: merchants.data?.map((merchant) => merchant.name),
    optionsError: [members, categories, tags, methods, merchants].some(
      (query) => query.isError,
    ),
  };
}
