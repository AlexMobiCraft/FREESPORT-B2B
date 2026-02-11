# Frontend Architecture

## Executive Summary
Next.js 15 application using the App Router architecture. It implements a responsive e-commerce interface with Server-Side Rendering (SSR) for SEO and performance.

## Technology Stack
- **Framework**: Next.js 15.5.7 (App Router)
- **Language**: TypeScript 5.0+
- **Styling**: Tailwind CSS 4.0
- **State Management**: Zustand (Client state) + React Query/SWR (Server state patterns)

## Key Concepts

### Theme System
The application supports multiple themes via Route Groups:
- `(blue)`: Default B2B/B2C theme.
- `(electric)`: Experimental/Demo theme.

### Component Architecture
Follows Atomic Design principles adapted for React:
- **UI**: Pure, presentational components (`src/components/ui`).
- **Business**: Domain-aware components (`src/components/business`).
- **Layout**: Structural shells (`src/components/layout`).

### Data Fetching
- **Server Components**: Fetch data directly (no API roundtrip if co-located) or via Internal API.
- **Client Components**: Use API Service layer (`src/services/`) with Axios.

## Detailed Documentation
- [Frontend Spec](./front-end-spec.md)
- [UX Design](./4-ux-design/)
