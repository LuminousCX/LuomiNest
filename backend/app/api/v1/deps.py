"""FastAPI 依赖注入占位。

认证由 app.security.auth.middleware.luomi_auth_middleware 在中间件层统一处理，
所有 /api/* 请求自动验证 Bearer Token，无需在路由层重复 Depends。

如未来需要细粒度权限控制（如管理员路由），可在此添加 Depends 依赖，
并通过 request.state.user 读取中间件写入的认证主体。
"""
