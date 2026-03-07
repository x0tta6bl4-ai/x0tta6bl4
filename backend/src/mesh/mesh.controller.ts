import {
  Body,
  Controller,
  Get,
  Param,
  Post,
  UseGuards,
  UseInterceptors,
  HttpCode,
  HttpStatus,
} from '@nestjs/common';
import { Throttle } from '@nestjs/throttler';
import { MeshService } from './mesh.service';
import { RegisterNodeDto } from './dto/register-node.dto';
import { HealRequestDto } from './dto/heal-request.dto';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { PrometheusInterceptor } from '../metrics/prometheus.interceptor';

@Controller('mesh')
@UseGuards(JwtAuthGuard)
@UseInterceptors(PrometheusInterceptor)
export class MeshController {
  constructor(private readonly meshService: MeshService) {}

  /**
   * POST /mesh/nodes
   * Register a new mesh node. Returns the node record with generated join token.
   */
  @Post('nodes')
  @HttpCode(HttpStatus.CREATED)
  @Throttle({ default: { limit: 20, ttl: 60_000 } })
  async registerNode(@Body() dto: RegisterNodeDto) {
    return this.meshService.registerNode(dto);
  }

  /**
   * GET /mesh/topology
   * Returns current mesh topology (nodes + edges). Response cached for 10 s.
   */
  @Get('topology')
  @Throttle({ default: { limit: 100, ttl: 60_000 } })
  async getTopology() {
    return this.meshService.getTopology();
  }

  /**
   * GET /mesh/nodes/:id/health
   * Live health probe for a specific node.
   */
  @Get('nodes/:id/health')
  @Throttle({ default: { limit: 60, ttl: 60_000 } })
  async getNodeHealth(@Param('id') id: string) {
    return this.meshService.getNodeHealth(id);
  }

  /**
   * POST /mesh/heal
   * Trigger a manual self-healing event for a target node.
   */
  @Post('heal')
  @HttpCode(HttpStatus.ACCEPTED)
  @Throttle({ default: { limit: 10, ttl: 60_000 } })
  async triggerHeal(@Body() dto: HealRequestDto) {
    return this.meshService.triggerHeal(dto);
  }
}
