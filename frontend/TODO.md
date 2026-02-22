# TODO: Replace react-beautiful-dnd with @dnd-kit/core in RubricBuilder

- [ ] Add @dnd-kit/core dependency to package.json
- [ ] Refactor src/components/rubrics/RubricBuilder.tsx:
  - Remove react-beautiful-dnd imports and usage
  - Implement drag-and-drop using @dnd-kit/core hooks and components
  - Update drag handle implementation to use @dnd-kit/core
  - Adjust drag end handler for @dnd-kit/core
- [ ] Test drag-and-drop reorder functionality
- [ ] Verify form behavior and UI styling remain consistent
- [ ] Remove react-beautiful-dnd package from dependencies
- [ ] Final testing (critical-path or thorough as per user preference)
