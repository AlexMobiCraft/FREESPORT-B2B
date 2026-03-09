#!/bin/bash

# Fix unused activeTabContent in Tabs.tsx
sed -i 's/const activeTabContent = tabs\.find((tab) => tab\.id === activeTab)?.content;/\/\/ Active tab content rendered in Tab Panels below/' src/components/ui/Tabs/Tabs.tsx

# Fix unused fireEvent in Input test
sed -i '7d' src/components/ui/Input/__tests__/Input.test.tsx

echo "Lint fixes applied"
