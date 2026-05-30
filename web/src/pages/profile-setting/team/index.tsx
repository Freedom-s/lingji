import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Table, TableBody, TableCell, TableRow } from '@/components/ui/table';
import { ChevronDown, MoreVertical, Plus, UserPlus } from 'lucide-react';

interface TeamMember {
  email: string;
  name: string;
  role: string;
}

const TeamManagement = () => {
  const teamMembers: TeamMember[] = [
    { email: 'yifanwu92@gmail.com', name: 'Yifan Wu', role: 'Admin' },
    { email: 'yifanwu92@gmail.com', name: 'Yifan Wu', role: 'Admin' },
  ];

  const stats = {
    project: 1,
    token: '1,000',
    storage: '1GB',
  };

  return (
    <div className="p-8 ">
      <div className=" mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-4xl font-bold">团队管理</h1>
          <Button variant={'tertiary'} size={'sm'}>
            <Plus className="mr-2 h-4 w-4" />
            创建团队
          </Button>
        </div>

        <div className="mb-8">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-2xl font-semibold">Yifan 的团队</h2>
            <Button variant="secondary" size="icon">
              <ChevronDown className="h-4 w-4" />
            </Button>
          </div>

          <Card className="border-0 p-6 mb-6 bg-colors-background-inverse-weak">
            <div className="grid grid-cols-3 gap-8">
              <div>
                <p className="text-sm text-gray-400 mb-2">项目</p>
                <p className="text-2xl font-semibold">{stats.project}</p>
              </div>
              <div>
                <p className="text-sm text-gray-400 mb-2">Token</p>
                <p className="text-2xl font-semibold">{stats.token}</p>
              </div>
              <div>
                <p className="text-sm text-gray-400 mb-2">存储空间</p>
                <p className="text-2xl font-semibold">{stats.storage}</p>
              </div>
            </div>
          </Card>

          <Card className="border-0 p-6 bg-colors-background-inverse-weak">
            <Table>
              <TableBody>
                {teamMembers.map((member, idx) => (
                  <TableRow key={idx}>
                    <TableCell>{member.email}</TableCell>
                    <TableCell>{member.name}</TableCell>
                    <TableCell className="flex items-center justify-end">
                      <span className="text-colors-text-core-standard">
                        {member.role}
                      </span>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon">
                            <MoreVertical className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem>编辑</DropdownMenuItem>
                          <DropdownMenuItem className="text-red-600">
                            移除
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            <Button variant="outline" className="mt-6 ">
              <UserPlus className="mr-2 h-4 w-4" />
              邀请成员
            </Button>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default TeamManagement;
