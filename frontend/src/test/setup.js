import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => cleanup())

// jsdom has no layout engine; components that scroll to a citation call this.
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView || (() => {})
