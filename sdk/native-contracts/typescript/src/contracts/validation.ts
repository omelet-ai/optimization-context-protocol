import { z, type ZodIssue, type ZodType } from 'zod';

export interface ContractValidationIssue {
  path: string;
  message: string;
  code: string;
}

export type ContractValidationResult<T> =
  | {
      valid: true;
      data: T;
      issues: [];
    }
  | {
      valid: false;
      issues: ContractValidationIssue[];
    };

export const RequiredUnknownSchema = z.unknown().refine((value) => value !== undefined, {
  message: 'Required',
});

export function contractIssuesFromZod(issues: ZodIssue[]): ContractValidationIssue[] {
  return issues.map((issue) => ({
    path: issue.path.length > 0 ? issue.path.map(String).join('.') : 'root',
    message: issue.message,
    code: issue.code,
  }));
}

export function validateContractSchema<T>(
  schema: ZodType<T, unknown>,
  value: unknown
): ContractValidationResult<T> {
  const result = schema.safeParse(value);

  if (result.success) {
    return {
      valid: true,
      data: result.data,
      issues: [],
    };
  }

  return {
    valid: false,
    issues: contractIssuesFromZod(result.error.issues),
  };
}
