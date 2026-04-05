/* 这个文件负责生成稳定的前端回跳地址，并保持当前访问主机名一致。 */

/* 生成稳定的绝对回跳地址，并保留当前访问主机名。 */
export function buildRedirectUrl(request: Request, targetPath: string): URL {
  const currentUrl = new URL(request.url);
  const forwardedProto = request.headers.get("x-forwarded-proto")?.trim() || currentUrl.protocol.replace(":", "");
  const forwardedHost = request.headers.get("x-forwarded-host")?.trim() || request.headers.get("host")?.trim() || currentUrl.host;
  return new URL(targetPath, `${forwardedProto}://${forwardedHost}`);
}
