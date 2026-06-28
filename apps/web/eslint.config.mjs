import base from '@repo/eslint-config';
import nextCoreWebVitals from 'eslint-config-next/core-web-vitals';
import nextTypescript from 'eslint-config-next/typescript';

// Next 16 ships native flat configs, so we spread them directly. (The older
// FlatCompat.extends('next/...') bridge crashes with a circular-reference error
// against eslint 9 + eslint-config-next 16.)
const eslintConfig = [...base, ...nextCoreWebVitals, ...nextTypescript];

export default eslintConfig;
