import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

afterEach(()=>cleanup())
Object.defineProperty(URL,'createObjectURL',{value:vi.fn(()=> 'blob:test-image'),writable:true})
Object.defineProperty(URL,'revokeObjectURL',{value:vi.fn(),writable:true})
